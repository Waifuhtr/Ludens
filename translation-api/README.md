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

A batching-optimized translation API for [tencent/Hy-MT2-7B-GGUF](https://huggingface.co/tencent/Hy-MT2-7B-GGUF),
built to run as a Hugging Face Space Docker app on an 8 vCPU / 32 GB RAM
instance.

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
  "target_lang": "tr",
  "preserve_placeholders": true
}
```
```json
{ "translation": "En yakın iksir dükkanı nerede?", "elapsed_seconds": 0.41 }
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
| `glossary` | object, optional | `{"HP": "Can Puanı"}` — forces specific term translations |
| `preserve_placeholders` | bool, default `true` | instructs the model to never touch `\N[1]`, `\V[1]`, `{var}`, `%s`, `%1`, etc. — important for RPG Maker / game strings |

### Auth
Set the `API_KEY` env var on the Space to require an `X-API-Key` header on
`/translate*`. Leave empty (default) to disable auth.

## Configuration (env vars)

| var | default | meaning |
|---|---|---|
| `MODEL_FILE` | `Hy-MT2-7B-Q4_K_M.gguf` | switch to `HY-MT2-7B-Q6_K.gguf` or `HY-MT2-7B-Q8_0.gguf` for higher quality / slower |
| `THREADS` | `8` | CPU threads for llama-server |
| `PARALLEL_SLOTS` | `8` | concurrent generation slots (continuous batching) |
| `CTX_SIZE` | `16384` | total context, split across `PARALLEL_SLOTS` slots |
| `MAX_TOKENS` | `512` | max output tokens per translation |
| `MAX_BATCH_SIZE` | `200` | max items accepted per `/translate/batch` call |
| `TEMPERATURE`/`TOP_P`/`TOP_K`/`REPEAT_PENALTY` | `0.7`/`0.6`/`20`/`1.05` | Hy-MT2 7B recommended sampling params |
| `API_KEY` | *(empty)* | optional shared secret for `X-API-Key` |

## Deploying

1. On [huggingface.co/new-space](https://huggingface.co/new-space), choose
   **Docker** as the SDK, then push this folder's contents (or upload via
   the web UI / `huggingface_hub`).
2. In the Space's **Settings → Hardware**, select a CPU tier with 8 vCPU /
   32 GB RAM (this needs to be set manually — it's a paid tier and isn't
   controlled by any file in this repo).
3. First boot downloads the ~4.6 GB GGUF file, so the first request after a
   cold start can take a few minutes; enable **persistent storage** in Space
   settings to avoid re-downloading on every restart.

## Local testing

```bash
docker build -t hy-mt2-api .
docker run -p 7860:7860 --cpus 8 --memory 32g hy-mt2-api
```

Then open `test-ui/index.html` in a browser, point it at
`http://localhost:7860`, and use it to benchmark single vs. batch requests.
