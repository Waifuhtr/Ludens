import os


def _int(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


def _float(name: str, default: float) -> float:
    return float(os.environ.get(name, default))


MODEL_REPO = os.environ.get("MODEL_REPO", "tencent/Hy-MT2-7B-GGUF")
MODEL_FILE = os.environ.get("MODEL_FILE", "Hy-MT2-7B-Q4_K_M.gguf")
MODEL_DIR = os.environ.get("MODEL_DIR", "/app/models")

LLAMA_SERVER_HOST = os.environ.get("LLAMA_SERVER_HOST", "127.0.0.1")
LLAMA_SERVER_PORT = _int("LLAMA_SERVER_PORT", 8080)
LLAMA_SERVER_URL = f"http://{LLAMA_SERVER_HOST}:{LLAMA_SERVER_PORT}"

# Matches Hy-MT2 1.8B/7B recommended sampling params from the model card.
TEMPERATURE = _float("TEMPERATURE", 0.7)
TOP_P = _float("TOP_P", 0.6)
TOP_K = _int("TOP_K", 20)
REPEAT_PENALTY = _float("REPEAT_PENALTY", 1.05)
MAX_TOKENS = _int("MAX_TOKENS", 512)

# --parallel value the llama-server was started with; also used to bound
# how many translation requests this gateway keeps in flight at once so
# requests queue instead of overwhelming the server's slots.
PARALLEL_SLOTS = _int("PARALLEL_SLOTS", 8)

MAX_BATCH_SIZE = _int("MAX_BATCH_SIZE", 200)
REQUEST_TIMEOUT_SECONDS = _float("REQUEST_TIMEOUT_SECONDS", 120.0)

# Optional shared-secret auth for the public gateway. Empty = disabled.
API_KEY = os.environ.get("API_KEY", "")

PORT = _int("PORT", 7860)
