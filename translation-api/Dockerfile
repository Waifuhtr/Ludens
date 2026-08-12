# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Stage 1: build llama-server from source.
#
# Why from source: the default model tencent/Hy-MT2-7B-GGUF needs the "STQ1_0"
# ggml quant kernel from https://github.com/ggml-org/llama.cpp/pull/22836,
# which is NOT merged into llama.cpp master yet. A stock llama.cpp (or pip
# llama-cpp-python) compiles fine but cannot load this GGUF. We clone master
# and cherry-pick the 3 commits of that PR; the cherry-pick is skipped
# automatically once upstream merges it (detected by grepping for
# GGML_TYPE_STQ1_0). The optional Rosetta model needs none of this - it is a
# Gemma 3 fine-tune that stock llama.cpp already runs.
# ---------------------------------------------------------------------------
FROM debian:bookworm-slim AS builder

ARG LLAMA_CPP_REF=master

# Bounded compile parallelism - this is what made earlier builds hang.
# `-j$(nproc)` reads the *host's* core count on a Hugging Face build worker
# (dozens of cores) while the worker's memory is capped far lower, so dozens
# of concurrent g++ processes thrash it: the build froze at 24% for 5+ hours
# and died with no error message. At -j2 peak memory stays around 3 GB and the
# llama-server target finishes in roughly 10 minutes. Raise via
# --build-arg BUILD_JOBS=4 only if you know the builder has RAM to spare.
ARG BUILD_JOBS=2

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake git ca-certificates pkg-config \
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

# BUILD_SHARED_LIBS=OFF produces one self-contained llama-server instead of a
# binary plus libllama.so / libggml*.so - the runtime stage copies a single
# file, so a shared build would have died at startup on a missing .so.
# LLAMA_BUILD_UI=OFF skips the embedded web UI, which otherwise downloads a
# tarball from huggingface.co during the build (it was already failing over to
# a fallback URL in the logs) - the FastAPI gateway is the only frontend here.
# GGML_NATIVE=OFF + GGML_AVX2=ON: the build worker's CPU is not the CPU the
# Space runs on, so target a portable AVX2 baseline rather than -march=native.
# Static libstdc++/libgcc so the binary does not depend on the builder image's
# GCC runtime matching the (newer) runtime image's.
RUN cmake -B build \
      -DCMAKE_BUILD_TYPE=Release \
      -DBUILD_SHARED_LIBS=OFF \
      -DLLAMA_CURL=OFF \
      -DLLAMA_BUILD_UI=OFF \
      -DLLAMA_BUILD_TESTS=OFF \
      -DLLAMA_BUILD_EXAMPLES=OFF \
      -DGGML_NATIVE=OFF \
      -DGGML_AVX2=ON \
      -DCMAKE_EXE_LINKER_FLAGS="-static-libstdc++ -static-libgcc" \
    && cmake --build build --config Release -j"${BUILD_JOBS}" --target llama-server

# ---------------------------------------------------------------------------
# Stage 2: runtime image (FastAPI gateway + llama-server binary)
# ---------------------------------------------------------------------------
FROM python:3.11-slim

# libgomp1 = OpenMP runtime, the only shared library the static llama-server
# still needs beyond glibc. curl is used by entrypoint.sh's readiness probe.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /build/build/bin/llama-server /app/llama-server

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY test-ui ./test-ui
COPY entrypoint.sh chat-template-rosetta.jinja ./
# --version is a real build-time smoke test: it fails the build if the binary
# cannot start (e.g. a missing shared library), instead of letting the Space
# deploy and only then crash on first request.
RUN chmod +x /app/llama-server /app/entrypoint.sh \
    && /app/llama-server --version

ENV MODEL_REPO=tencent/Hy-MT2-7B-GGUF \
    MODEL_FILE=Hy-MT2-7B-Q4_K_M.gguf \
    MODEL_DIR=/app/models \
    LLAMA_SERVER_HOST=127.0.0.1 \
    LLAMA_SERVER_PORT=8080 \
    THREADS=8 \
    PARALLEL_SLOTS=8 \
    CTX_SIZE=16384 \
    MAX_TOKENS=512 \
    MAX_BATCH_SIZE=200 \
    API_KEY="" \
    PORT=7860

EXPOSE 7860

CMD ["./entrypoint.sh"]
