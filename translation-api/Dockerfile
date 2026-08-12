# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Stage 1: build llama-server from source.
#
# IMPORTANT: tencent/Hy-MT2-7B-GGUF depends on a custom "STQ" ggml kernel
# that shipped in https://github.com/ggml-org/llama.cpp/pull/22836. A pip
# install of llama-cpp-python pins an older llama.cpp commit and will very
# likely NOT be able to load this GGUF (unknown tensor type / load error).
# Building llama.cpp from source here (default: the `main` branch, which
# should have the PR merged by now) avoids that. If it hasn't landed yet,
# rebuild with:
#   docker build --build-arg LLAMA_CPP_REF=refs/pull/22836/head -t hy-mt2-api .
# ---------------------------------------------------------------------------
FROM debian:bookworm-slim AS builder

ARG LLAMA_CPP_REF=main

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake git ca-certificates libcurl4-openssl-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
RUN git clone https://github.com/ggml-org/llama.cpp.git . \
    && if [ "$LLAMA_CPP_REF" != "main" ]; then \
         git fetch origin "$LLAMA_CPP_REF" && git checkout FETCH_HEAD; \
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
