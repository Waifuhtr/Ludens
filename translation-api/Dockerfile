# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# GPU image: the official prebuilt llama.cpp CUDA server plus this repo's
# FastAPI gateway. Nothing is compiled here.
#
# Earlier revisions built llama.cpp from source and cherry-picked the "STQ1_0"
# quant kernel from PR #22836, because the Hy-MT2 model card warns its GGUFs
# depend on that kernel. Reading the actual tensor tables shows that is not
# true for the quants this project uses: Hy-MT2-7B-Q4_K_M and
# Hy-MT2-1.8B-Q4_K_M are both 354 tensors of plain Q4_K / Q6_K / F32 on the
# `hunyuan-dense` architecture, all of which stock llama.cpp already supports.
# (The STQ warning applies to the separate 2-bit / 1.25-bit repos.) Dropping
# the source build removes 10-60 minutes of compiling per deploy and with it
# every build failure this project has hit - OOM-thrashed builders, missing
# git identity, a COPY of a file that wasn't in the context.
#
# The tag is pinned rather than floating on :server-cuda so a redeploy cannot
# silently land on a different llama.cpp. b10398 postdates `hunyuan-dense`
# support, and llama.cpp's default CUDA architecture list includes 75-virtual,
# which covers the T4 (sm_75) this targets - as PTX, so the driver JIT-compiles
# it once on first model load. Bump with:
#   --build-arg LLAMA_CPP_IMAGE=ghcr.io/ggml-org/llama.cpp:server-cuda-bNNNNN
# ---------------------------------------------------------------------------
ARG LLAMA_CPP_IMAGE=ghcr.io/ggml-org/llama.cpp:server-cuda-b10398
FROM ${LLAMA_CPP_IMAGE}

# The base image carries llama-server and its shared libraries in /app and
# little else - notably no Python. Its own layer so it stays cached whatever
# happens to the application below.
RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies before source, so editing app/ or test-ui/ rebuilds only the
# last few (instant) layers instead of reinstalling everything.
# --break-system-packages: the CUDA base is Ubuntu, whose system Python is
# PEP 668 "externally managed"; llama.cpp's own images install the same way.
COPY requirements.txt .
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt

COPY app ./app
COPY test-ui ./test-ui
COPY entrypoint.sh ./

# Written inline rather than COPYed so the build cannot fail with "not found"
# just because this one extra file didn't make it into the build context -
# which is exactly what broke a previous deploy. Must stay identical to
# chat-template-rosetta.jinja in the repo; see the comment there for why the
# template exists at all.
RUN cat <<'CHAT_TEMPLATE' > /app/chat-template-rosetta.jinja
{{- bos_token -}}
{%- for m in messages -%}
{%- if m['role'] == 'system' -%}
{{- '<start_of_turn>instruction\n' -}}{{- m['content'] | trim -}}{{- '<end_of_turn>\n' -}}
{%- endif -%}
{%- endfor -%}
{%- for m in messages -%}
{%- if m['role'] == 'user' -%}
{{- '<start_of_turn>source\n' -}}{{- m['content'] | trim -}}{{- '<end_of_turn>\n' -}}
{%- endif -%}
{%- endfor -%}
{%- if add_generation_prompt -%}
{{- '<start_of_turn>translation\n' -}}
{%- endif -%}
CHAT_TEMPLATE

# Deliberately not `llama-server --version` as a smoke test any more: the
# binary now comes from an image that is already known-good, while the build
# worker has no GPU, so touching the CUDA backend at build time risks failing
# a build that would have run fine.
RUN chmod +x /app/entrypoint.sh && test -x /app/llama-server

ENV MODEL_REPO=tencent/Hy-MT2-7B-GGUF \
    MODEL_FILE=Hy-MT2-7B-Q4_K_M.gguf \
    MODEL_DIR=/app/models \
    GLOSSARY_FILE="" \
    DEFAULT_STYLE="" \
    GROUP_SIZE=10 \
    LLAMA_SERVER_HOST=127.0.0.1 \
    LLAMA_SERVER_PORT=8080 \
    GPU_LAYERS=all \
    THREADS=4 \
    PARALLEL_SLOTS=16 \
    CTX_SIZE=32768 \
    MAX_TOKENS=512 \
    MAX_BATCH_SIZE=200 \
    API_KEY="" \
    PORT=7860

# The base image sets LLAMA_ARG_HOST=0.0.0.0, which llama-server reads as a
# fallback for --host. entrypoint.sh passes --host explicitly, but overriding
# the variable too means the inference server stays loopback-only even if that
# flag is ever dropped: only the gateway on $PORT should be reachable.
ENV LLAMA_ARG_HOST=127.0.0.1

EXPOSE 7860

# The base image's ENTRYPOINT is /app/llama-server. Left in place, a CMD here
# would be appended to it and Docker would run `llama-server ./entrypoint.sh`.
ENTRYPOINT ["/app/entrypoint.sh"]

# Long start period: a cold start downloads several GB of GGUF before the
# gateway answers. /health returns 200 while the model is still loading, so
# this only fails if the process is genuinely dead.
HEALTHCHECK --start-period=15m --interval=1m --timeout=10s \
    CMD curl -fsS http://localhost:7860/health || exit 1
