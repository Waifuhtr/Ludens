# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Stage 1: build llama-server from source.
#
# IMPORTANT: tencent/Hy-MT2-7B-GGUF depends on the "STQ1_0" ggml quant kernel
# from https://github.com/ggml-org/llama.cpp/pull/22836, which is NOT merged
# into llama.cpp's `master` as of this writing (confirmed by cloning master
# and grepping for GGML_TYPE_STQ1_0 - absent). Plain `pip install
# llama-cpp-python` or a vanilla `git clone` of master will compile fine but
# fail to load this GGUF at runtime ("unknown tensor type" / load error).
#
# Fix: clone master, then cherry-pick the 3 commits that make up the PR
# (verified below to cherry-pick cleanly with zero conflicts onto current
# master):
#   5503c4b8  Add support for STQ_0 ternary quantization
#   5165daa8  rename STQ_0 to STQ1_0 according to reviewer suggestion
#   1e411d8f  ggml-cpu : fix STQ1_0 CI failures
# The build skips the cherry-pick automatically once upstream merges the
# PR (detected via a grep for GGML_TYPE_STQ1_0), so this stays correct
# without edits. To pin a specific base commit/branch instead of master,
# use --build-arg LLAMA_CPP_REF=<ref>.
# ---------------------------------------------------------------------------
FROM debian:bookworm-slim AS builder

ARG LLAMA_CPP_REF=master

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake git ca-certificates libcurl4-openssl-dev libssl-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
RUN git config --global user.email "build@hy-mt2-api.local" \
    && git config --global user.name "hy-mt2-api Docker build" \
    && git clone https://github.com/ggml-org/llama.cpp.git . \
    && if [ "$LLAMA_CPP_REF" != "master" ]; then \
         git fetch origin "$LLAMA_CPP_REF" && git checkout FETCH_HEAD; \
       fi \
    && if grep -q GGML_TYPE_STQ1_0 ggml/include/ggml.h; then \
         echo "STQ1_0 kernel already present upstream, skipping cherry-pick"; \
       else \
         echo "STQ1_0 kernel missing, cherry-picking from PR #22836" \
         && git fetch origin refs/pull/22836/head:stq-pr \
         && git cherry-pick -x \
              5503c4b816da60cafd3cfc275dd9f50f079e0cf4 \
              5165daa88c2a36a663534d6cbefd6e13b3fe4623 \
              1e411d8f5a1e23525fa3265dfb4bd76265465397; \
       fi

# GGML_NATIVE=OFF because the Docker build machine's CPU may differ from the
# machine the image eventually runs on; GGML_AVX2=ON targets the common
# baseline for modern cloud/Space CPUs. Drop it if you hit "illegal
# instruction" at runtime on older hardware.
RUN cmake -B build \
      -DCMAKE_BUILD_TYPE=Release \
      -DLLAMA_CURL=OFF \
      -DGGML_NATIVE=OFF \
      -DGGML_AVX2=ON \
    && cmake --build build --config Release -j"$(nproc)" --target llama-server

# ---------------------------------------------------------------------------
# Stage 2: runtime image (FastAPI gateway + llama-server binary)
# ---------------------------------------------------------------------------
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 libcurl4 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /build/build/bin/llama-server /app/llama-server

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY entrypoint.sh .
RUN chmod +x /app/llama-server /app/entrypoint.sh

ENV MODEL_REPO=tencent/Hy-MT2-7B-GGUF \
    MODEL_FILE=Hy-MT2-7B-Q4_K_M.gguf \
    MODEL_DIR=/app/models \
    LLAMA_SERVER_HOST=127.0.0.1 \
    LLAMA_SERVER_PORT=8080 \
    THREADS=8 \
    PARALLEL_SLOTS=8 \
    CTX_SIZE=16384 \
    MAX_TOKENS=512 \
    TEMPERATURE=0.7 \
    TOP_P=0.6 \
    TOP_K=20 \
    REPEAT_PENALTY=1.05 \
    MAX_BATCH_SIZE=200 \
    API_KEY="" \
    PORT=7860

EXPOSE 7860

CMD ["./entrypoint.sh"]
