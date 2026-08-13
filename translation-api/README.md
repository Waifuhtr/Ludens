---
title: Hy-MT2 Translation API
emoji: 🌐
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
license: apache-2.0
---

# Hy-MT2 Translation API

A batching-optimized translation API for the
[Hy-MT2](https://huggingface.co/collections/tencent/hy-mt2) GGUF models,
built to run as a Hugging Face Space Docker app on an 8 vCPU / 32 GB RAM
instance. Defaults to **Hy-MT2-1.8B** for throughput; the 7B is one env var
away. Beyond raw translation it carries the machinery a 50k-string game
localisation actually needs — a project glossary, a pinned register, and
passthrough for control-code-only lines. See
[Keeping 50k strings consistent](#keeping-50k-strings-consistent).

## How it works

- **Inference engine**: `llama-server` (from [llama.cpp](https://github.com/ggml-org/llama.cpp)),
  compiled from source in the Docker build. This GGUF depends on the
  `STQ1_0` quant kernel from
  [PR #22836](https://github.com/ggml-org/llama.cpp/pull/22836), which is
  **not yet merged into llama.cpp `master`** (verified directly) — a plain
  `pip install llama-cpp-python` or a vanilla clone of master will compile
  but fail to load this GGUF at runtime. The `Dockerfile` clones master and
  cherry-picks the 3 commits that make up that PR (verified to apply
  cleanly, zero conflicts); it auto-skips the cherry-pick once upstream
  merges it, so no edits are needed later.
  The build is pinned to `-j2` (`BUILD_JOBS`) — see
  [Build notes](#build-notes), this is what stopped the build from hanging.
  It's started with `--threads 8 --parallel 8 --cont-batching`, which uses
  llama.cpp's continuous batching to combine multiple in-flight requests'
  forward passes into shared compute instead of running them one at a time.
  This is the real mechanism behind the "batch instead of one-by-one"
  optimization you asked for — the 8 cores get fed one bigger batched matmul
  per step instead of 8 independent tiny ones.
- **Gateway**: a small FastAPI app (`app/main.py`) in front of it, which
  builds the Hy-MT2 instruction-format prompt (see `app/translation.py`) for
  each string and fans batch requests out concurrently to `llama-server`,
  bounded by `PARALLEL_SLOTS` so requests queue cleanly instead of
  overloading the model.
- Chat formatting uses the GGUF's embedded Jinja chat template
  (`llama-server --jinja`), matching the model card's documented usage.

## Endpoints

### `GET /health`
Backend status check.

### `GET /languages`
Returns the map of supported language codes → names (the 33 languages
Hy-MT2 documents support for).

### `POST /translate` — single string
```json
{
  "text": "Where is the nearest potion shop?",
  "target_lang": "tr"
}
```
```json
{ "translation": "En yakın iksir dükkanı nerede?", "elapsed_seconds": 4.82 }
```

### `POST /translate/batch` — many strings in one call (recommended: 50-100 per call)
```json
{
  "texts": ["Hello!", "Welcome!", "Potion", "Attack"],
  "target_lang": "tr"
}
```
```json
{
  "translations": [
    { "original": "Hello!", "translation": "Merhaba!" },
    { "original": "Welcome!", "translation": "Hoş geldin!" },
    { "original": "Potion", "translation": "İksir" },
    { "original": "Attack", "translation": "Saldırı" }
  ],
  "count": 4,
  "elapsed_seconds": 0.9,
  "items_per_second": 4.44
}
```

For 50,000 game strings: split them into chunks of ~50-100 and call
`/translate/batch` per chunk (either sequentially or a few chunks at a time)
rather than one string per HTTP call. `MAX_BATCH_SIZE` (default 200) is a
server-side safety cap on a single call.

**Request fields common to both endpoints:**
| field | type | notes |
|---|---|---|
| `target_lang` | string | ISO code (`tr`, `en`, `ja`, ...) or full name |
| `source_lang` | string, optional | omit to let the model auto-detect |
| `style` | string, optional | e.g. `"casual, playful"` — injected as a style instruction |
| `glossary` | object, optional | `{"HP": "Can Puanı"}` — merged on top of the project glossary file (see `GLOSSARY_FILE`) |
| `context` | string, optional | background about the scene, injected with the model card's "Background Information" template. Weak in practice — see [Verified behaviour](#verified-behaviour) |
| `preserve_placeholders` | bool, default `false` | adds an explicit "keep placeholders verbatim" clause. **Leave it off**: Hy-MT2 already preserves `\V[1]`, `%1`, `{var}` etc. on its own (measured — see [Verified behaviour](#verified-behaviour)), so the clause only costs prompt tokens |

### `POST /translate/document` — ordered lines of one scene
Same fields as `/translate/batch`, plus `group_size`. Packs consecutive lines
into one generation so the model sees the surrounding dialogue instead of
each line alone. **Slower than `/translate/batch` (~25%) but more
consistent** — use it for dialogue, not for bulk UI strings. Untranslatable
lines are kept out of the group and copied through.

```json
{ "texts": ["...", "..."], "target_lang": "tr", "group_size": 10 }
```
The response adds `groups`, `group_size` and `regrouped_fallbacks`. A group
whose markers come back wrong is silently re-run one line at a time, so lines
can never end up shifted; a climbing `regrouped_fallbacks` means `group_size`
is too large for the model in use.

### Auth
Set the `API_KEY` env var on the Space to require an `X-API-Key` header on
`/translate*`. Leave empty (default) to disable auth.

## Configuration (env vars)

| var | default | meaning |
|---|---|---|
| `MODEL_REPO` | `tencent/Hy-MT2-1.8B-GGUF` | set to `tencent/Hy-MT2-7B-GGUF` (with a matching `MODEL_FILE`) to trade ~4x throughput for noticeably better prose |
| `MODEL_FILE` | `Hy-MT2-1.8B-Q4_K_M.gguf` | `Hy-MT2-7B-Q4_K_M.gguf` with the 7B repo. Stay on `Q4_K_M`: lower-bit quants measured *slower* on CPU, see [Build notes](#build-notes) |
| `DEFAULT_STYLE` | *(empty)* | style applied when a request sends none. **The single most effective quality setting** — see [Keeping 50k strings consistent](#keeping-50k-strings-consistent) |
| `GLOSSARY_FILE` | *(empty)* | path to a JSON `{"term": "translation"}` file; only the terms occurring in a given string are attached to its prompt. See `glossary.example.json` |
| `GROUP_SIZE` | `10` | strings packed into one generation by `/translate/document` |
| `THREADS` | `8` | CPU threads for llama-server |
| `PARALLEL_SLOTS` | `8` | concurrent generation slots (continuous batching) |
| `CTX_SIZE` | `16384` | total context, split across `PARALLEL_SLOTS` slots |
| `MAX_TOKENS` | `512` | max output tokens per translation |
| `MAX_BATCH_SIZE` | `200` | max items accepted per `/translate/batch` call |
| `PROMPT_FORMAT` | inferred | `hy-mt2` or `rosetta` — see [Switching model family](#switching-model-family). Inferred from `MODEL_REPO`, so you rarely set it by hand |
| `TEMPERATURE`/`TOP_P`/`TOP_K`/`REPEAT_PENALTY` | per family | `0.7`/`0.6`/`20`/`1.05` for Hy-MT2 (its model card's values), `0.7`/`0.95`/`64`/`1.0` for Rosetta (Gemma 3 defaults) |
| `API_KEY` | *(empty)* | optional shared secret for `X-API-Key` |

## Deploying

1. On [huggingface.co/new-space](https://huggingface.co/new-space), choose
   **Docker** as the SDK, then push this folder's contents (or upload via
   the web UI / `huggingface_hub`).
2. In the Space's **Settings → Hardware**, select a CPU tier with 8 vCPU /
   32 GB RAM (this needs to be set manually — it's a paid tier and isn't
   controlled by any file in this repo).
3. First boot downloads the GGUF (~1.1 GB for the 1.8B default, ~4.6 GB for
   the 7B), so the first request after a cold start is slow; enable
   **persistent storage** in Space settings to avoid re-downloading on every
   restart.
4. Optional but recommended for a real localisation run: set `DEFAULT_STYLE`,
   and mount a glossary JSON and point `GLOSSARY_FILE` at it.

## Local testing

```bash
docker build -t hy-mt2-api .
docker run -p 7860:7860 --cpus 8 --memory 32g hy-mt2-api
```

Then open `test-ui/index.html` in a browser, point it at
`http://localhost:7860`, and use it to benchmark single vs. batch requests.

## Verified behaviour

The stack below was actually run end to end against
`Hy-MT2-7B-Q4_K_M.gguf` (real model, real llama-server built exactly as the
`Dockerfile` builds it) on a **4-core / 15 GB** box — smaller than the 8 vCPU
Space, so treat these as a floor, not a target.

- The STQ1_0 cherry-pick works: the model loads and generates. This was the
  whole open question, and it is settled.
- Translation quality spot-checks (EN→TR): `"Potion"` → `"İksir"`,
  `"Are you sure you want to quit the game?"` →
  `"Oyundan çıkmak istediğinizden emin misiniz?"`.
- **Placeholders survive untouched with no special instruction**:
  `"You have obtained \V[1] gold."` → `"\V[1] altın elde ettiniz."`, and
  `"Press %1 to open your inventory."` →
  `"Envanterinizi açmak için %1'e basın."`.
- `glossary` and `style` both take effect: with `{"gold": "altın", "HP": "Can
  Puanı"}` the model returned `"50 altınınız ve dolu Can Puanınız var."`;
  with style `medieval, formal`, `"Hey, watch out!"` → `"Ey dostum, dikkatli
  ol!"`.
- Throughput, 8 short game strings, 4 slots on 4 cores:
  **sequential 19.2 s vs. batch 12.2 s (1.58×)**. A 24-item batch of longer
  sentences ran at 0.34 items/s. Expect roughly double on 8 vCPU.

### 1.8B vs 7B, measured

The default is now **1.8B**. Same 10-line dialogue scene, 4 cores:

| model | time | throughput |
|---|---|---|
| Hy-MT2-7B Q4_K_M | 33.0 s | 0.30 items/s |
| Hy-MT2-1.8B Q4_K_M | 10.9 s | 0.92 items/s |
| Hy-MT2-1.8B Q4_K_M + passthrough + `DEFAULT_STYLE` | **7.9 s** | **1.27 items/s** |

That is **~4x** end to end, which on 8 vCPU puts 50,000 sentence-length
strings in the region of a few hours rather than a day.

The cost is real: 1.8B makes mistakes 7B does not — it rendered *"Her round
eyes…"* with English *Her* read as Turkish *her* ("every"), and turned a
vocative *"…, Michiru?"* into an object *"Michiru'yu"*. Set
`MODEL_REPO=tencent/Hy-MT2-7B-GGUF` and `MODEL_FILE=Hy-MT2-7B-Q4_K_M.gguf`
for anything where prose quality outranks throughput.

### A note on `preserve_placeholders`

An earlier version of this API sent a long "never translate `\N[..]`,
`{variable}`, `%s` …" instruction on every request, with that list spelled
out. Hy-MT2 is a pure translation model, not a general chat model: it
**translated the instruction** instead of following it, and short inputs were
destroyed outright — `"Potion"` came back as the Turkish text of the
instruction, with the actual word gone. Anything the model is meant to obey
has to live inside the single instruction line of the model card's documented
templates, never as its own paragraph in front of the source text. The flag
now defaults to off and, when enabled, adds one short clause with no literal
placeholder examples.

## Keeping 50k strings consistent

The failure mode on a big run is not a mistranslated word, it is the same
character sounding like two different people across a scene. Each string is
translated in isolation, so nothing carries register or terminology from one
line to the next. Four levers were built and measured on the 1.8B model; they
are listed in the order they are worth reaching for.

**1. `DEFAULT_STYLE` — the strong one.** Turkish forces a T/V choice on every
sentence and the model picks per line, so one line says *geç kaldın* and the
next *geç kaldınız*. Pinning the register fixes it globally:

```
DEFAULT_STYLE=casual spoken Turkish, informal second person singular (sen), never the formal siz form
```

| line | without | with |
|---|---|---|
| `You're thirty minutes late.` | Otuz dakika geç **kaldınız** | Otuz dakika geç **kaldın** |
| `You rest at the inn…` | geri **kazanırsınız** | **dinlen** ve … **tamamla** |

**2. `GLOSSARY_FILE` — for names and terms.** A project-wide JSON dictionary;
only terms occurring in a string are attached, so a 2000-entry glossary costs
nothing on a line that uses none of it. Verified: `potion`→`iksir`,
`HP`→`Can Puanı`, `inn`→`han` applied without the request sending any
glossary. Treat it as a strong hint, not a guarantee — in testing the model
kept `bar` instead of the requested `meyhane` on one line.

**3. Untranslatable-line passthrough — free, always on.** Lines that are only
control codes, numbers or punctuation (`\SE[1]\n[1].`, `%1`, `---`) never
reach the model. This is a correctness fix as much as a speed one: with a
style instruction attached, `\SE[1]\n[1].` came back as
`\SE[1]\n[1]. senin için` — words invented out of nothing. Game files are
full of such lines, and each one skipped is a whole generation saved.

**4. `/translate/document` — better flow, ~25% slower.** Grouped translation
did visibly fix register drift *before* `DEFAULT_STYLE` existed, and still
smooths sentence flow across a scene. With levers 1-3 in place its remaining
benefit is smaller, so it is opt-in.

`context` was also implemented and measured, and is the weak one: supplying a
scene description did not fix the formality drift and mostly changed word
choice. It stays available for domain hints, but do not expect much.

### Grouping did not turn out to be a speed win

Amortising the instruction prompt across a group sounds like it should be
faster. It is not, on CPU:

| mode | 40 lines, 4 slots | throughput |
|---|---|---|
| `/translate/batch` (one request per line) | **33.8 s** | **1.19 items/s** |
| `/translate/document`, `group_size=5` | 43.3 s | 0.92 items/s |
| `/translate/document`, `group_size=10` | 49.7 s | 0.80 items/s |

CPU inference is dominated by *decode*, not prompt prefill, and grouping does
not reduce the number of tokens generated — it just serialises ten
translations into one stream and gives up the parallelism of the other slots.
Continuous batching across slots beats packing more into a single request.

## Switching model family

Two prompt families are supported. `PROMPT_FORMAT` selects one; leaving it
unset infers it from `MODEL_REPO` (any repo whose name contains "rosetta"
gets `rosetta`, everything else `hy-mt2`), so changing the model is usually a
one-variable edit. `entrypoint.sh` applies the same rule, so the server flags
and the prompt builder can't drift apart.

- **`hy-mt2`** (default) — one user turn holding the instruction and the text,
  using the model card's templates.
- **`rosetta`** — [YanoljaNEXT-Rosetta](https://huggingface.co/yanolja/YanoljaNEXT-Rosetta-4B-2511-GGUF),
  a Gemma 3 translation fine-tune. Directives go in a `system` turn
  (`Tone:`, `Glossary:`, …) and only the source text in `user`; its chat
  template renames those roles to `instruction` / `source`. Set both:
  ```
  MODEL_REPO=yanolja/YanoljaNEXT-Rosetta-4B-2511-GGUF
  MODEL_FILE=Q5_K_M/YanoljaNEXT-Rosetta-4B-2511-bf16-q5_k_m.gguf
  ```

Rosetta ships a chat template that `llama-server` **cannot load**: it calls
the Jinja `default` filter on an object, which llama.cpp's minja engine does
not implement, and the server aborts at startup rather than degrade
(`Unknown (built-in) filter 'default' for type Object`). `chat-template-rosetta.jinja`
in this folder is a minja-compatible rewrite that renders identically for the
one-system-plus-one-user requests this API sends; `entrypoint.sh` passes it
via `--chat-template-file` whenever the format is `rosetta`.

### Measured: Rosetta was slower, so it is not the default

Same 10 lines of RPG dialogue, same box, same settings:

| Model | Time | Throughput |
|---|---|---|
| Hy-MT2-7B Q4_K_M | **33.0 s** | **0.30 items/s** |
| Rosetta-4B Q5_K_M | 39.7 s | 0.25 items/s |

Fewer parameters did not win here — Rosetta only publishes 5-bit and IQ
quants, and Q5_K_M moves more memory per token than Q4_K_M. It also dropped a
control code that Hy-MT2 kept (`\SE[1]I'm Michiru.` → `Ben Michiru'yum.`,
losing `\SE[1]`) and repeated a line; `preserve_placeholders: true` fixes the
dropped code but lengthens every prompt. Its own card notes it is tuned for
structured JSON/YAML/XML and that "performance on unstructured text may
vary", which is what dialogue is. Keep it in mind for structured content, not
for speed.

The same held for low-bit quantisation of Hy-MT2 itself: `Q3_K_M` measured
**60.1 s** against Q4_K_M's 33.0 s on that dialogue, nearly 2× slower.
llama.cpp's CPU kernels are far better optimised for Q4_K than for the
K-quants around it, so dropping bits is not a reliable speed lever here.

## Build notes

The Docker build compiles llama.cpp, which is the slow part. Earlier builds
**hung at 24% for 5+ hours and then died with no error message** — the giveaway
was that they stopped at exactly the same source file every time. Cause:
`-j$(nproc)` reads the *host's* core count on a Hugging Face build worker
while the worker's memory ceiling is much lower, so dozens of concurrent g++
processes thrash it into swap. Bounding it (`BUILD_JOBS=2`, plus
`LLAMA_BUILD_UI=OFF` so the build stops fetching a UI tarball over the
network) is the fix: the same target builds in **about 4 minutes at -j4** on a
4-core machine.

This cost is paid once — Docker layer caching skips the whole compile on
later deploys as long as you don't edit the `Dockerfile`. Editing only
`app/` or `test-ui/` rebuilds in seconds.

Two other latent problems were fixed at the same time:

- The old build produced a **shared** llama-server (`libllama.so`,
  `libggml*.so`) but the runtime stage copied only the executable, so even a
  successful build would have crashed at startup on a missing shared library.
  The build is now static (`BUILD_SHARED_LIBS=OFF`), one file, and
  `llama-server --version` runs as a build-time smoke test.
- `--mlock` is deprecated in current llama.cpp (superseded by `--load-mode`),
  so `entrypoint.sh` does not use it; the default mmap loading is right for a
  4.6 GB model on 32 GB of RAM.
