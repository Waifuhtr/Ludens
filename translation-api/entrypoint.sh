#!/usr/bin/env bash
set -euo pipefail

MODEL_PATH="${MODEL_DIR}/${MODEL_FILE}"

# python3, not python: the CUDA base image is Ubuntu and ships no `python`
# alias. Same reason the gateway is started with `python3 -m uvicorn` below.
if [ ! -f "$MODEL_PATH" ]; then
  echo "[entrypoint] Downloading ${MODEL_FILE} from ${MODEL_REPO} ..."
  echo "[entrypoint] (several GB - enable persistent storage on the Space so"
  echo "[entrypoint]  this does not repeat, on GPU time, at every cold start)"
  python3 -c "
from huggingface_hub import hf_hub_download
hf_hub_download(repo_id='${MODEL_REPO}', filename='${MODEL_FILE}', local_dir='${MODEL_DIR}')
"
else
  echo "[entrypoint] Found cached model at ${MODEL_PATH}"
fi

# Rosetta's own embedded template uses a Jinja filter llama.cpp's minja engine
# does not implement, and llama-server refuses to start rather than degrade -
# so that family gets the bundled, minja-compatible rewrite instead. Hy-MT2
# uses the template inside its GGUF.
# Same inference rule as app/config.py, so setting MODEL_REPO alone keeps the
# server flags and the prompt builder agreed on the format.
RESOLVED_FORMAT="${PROMPT_FORMAT:-}"
if [ -z "$RESOLVED_FORMAT" ]; then
  case "$(echo "$MODEL_REPO" | tr '[:upper:]' '[:lower:]')" in
    *rosetta*) RESOLVED_FORMAT="rosetta" ;;
    *)         RESOLVED_FORMAT="hy-mt2" ;;
  esac
fi

TEMPLATE_ARGS=()
case "$RESOLVED_FORMAT" in
  rosetta) TEMPLATE_ARGS=(--chat-template-file /app/chat-template-rosetta.jinja) ;;
esac

echo "[entrypoint] Starting llama-server (gpu-layers=${GPU_LAYERS:-all}, threads=${THREADS}, parallel=${PARALLEL_SLOTS}, ctx=${CTX_SIZE}) ..."
/app/llama-server \
  --model "$MODEL_PATH" \
  --host "${LLAMA_SERVER_HOST}" \
  --port "${LLAMA_SERVER_PORT}" \
  --gpu-layers "${GPU_LAYERS:-all}" \
  --threads "${THREADS}" \
  --threads-batch "${THREADS}" \
  --ctx-size "${CTX_SIZE}" \
  --parallel "${PARALLEL_SLOTS}" \
  --cont-batching \
  --jinja \
  "${TEMPLATE_ARGS[@]}" \
  --no-webui &
LLAMA_PID=$!

# Generous ceiling: on a T4 the first load also JIT-compiles the PTX shipped
# for sm_75, which the driver then caches.
echo "[entrypoint] Waiting for llama-server to become healthy ..."
for _ in $(seq 1 300); do
  if curl -sf "http://${LLAMA_SERVER_HOST}:${LLAMA_SERVER_PORT}/health" >/dev/null 2>&1; then
    echo "[entrypoint] llama-server is ready."
    break
  fi
  if ! kill -0 "$LLAMA_PID" 2>/dev/null; then
    echo "[entrypoint] llama-server exited unexpectedly, aborting." >&2
    exit 1
  fi
  sleep 2
done

echo "[entrypoint] Starting API gateway on port ${PORT} ..."
python3 -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" &
API_PID=$!

wait -n "$LLAMA_PID" "$API_PID"
