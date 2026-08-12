#!/usr/bin/env bash
set -euo pipefail

MODEL_PATH="${MODEL_DIR}/${MODEL_FILE}"

if [ ! -f "$MODEL_PATH" ]; then
  echo "[entrypoint] Downloading ${MODEL_FILE} from ${MODEL_REPO} ..."
  python -c "
from huggingface_hub import hf_hub_download
hf_hub_download(repo_id='${MODEL_REPO}', filename='${MODEL_FILE}', local_dir='${MODEL_DIR}')
"
else
  echo "[entrypoint] Found cached model at ${MODEL_PATH}"
fi

echo "[entrypoint] Starting llama-server (threads=${THREADS}, parallel=${PARALLEL_SLOTS}, ctx=${CTX_SIZE}) ..."
/app/llama-server \
  --model "$MODEL_PATH" \
  --host "${LLAMA_SERVER_HOST}" \
  --port "${LLAMA_SERVER_PORT}" \
  --threads "${THREADS}" \
  --threads-batch "${THREADS}" \
  --ctx-size "${CTX_SIZE}" \
  --parallel "${PARALLEL_SLOTS}" \
  --cont-batching \
  --jinja \
  --no-webui &
LLAMA_PID=$!

echo "[entrypoint] Waiting for llama-server to become healthy ..."
for _ in $(seq 1 150); do
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
uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" &
API_PID=$!

wait -n "$LLAMA_PID" "$API_PID"
