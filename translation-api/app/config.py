import os


def _int(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


def _float(name: str, default: float) -> float:
    return float(os.environ.get(name, default))


MODEL_REPO = os.environ.get("MODEL_REPO", "tencent/Hy-MT2-1.8B-GGUF")
MODEL_FILE = os.environ.get("MODEL_FILE", "Hy-MT2-1.8B-Q4_K_M.gguf")
MODEL_DIR = os.environ.get("MODEL_DIR", "/app/models")

# Optional JSON file of term -> translation applied to every request (only the
# terms that occur in a given string are attached). This is what keeps
# character names and game terms identical across a whole 50k-string run.
GLOSSARY_FILE = os.environ.get("GLOSSARY_FILE", "")

# Style applied when a request does not send its own. Measurably the strongest
# lever for register consistency: without it the model drifts between the
# formal and informal second person from one line to the next (Turkish
# siz/sen), which reads as two different characters. Example value:
#   "casual spoken Turkish, informal second person singular (sen)"
DEFAULT_STYLE = os.environ.get("DEFAULT_STYLE", "")

# Strings packed into a single generation by /translate/document. Bigger
# groups amortise the instruction prompt further and give the model more
# surrounding dialogue, but raise the cost of a group failing validation and
# being retried one string at a time.
GROUP_SIZE = _int("GROUP_SIZE", 10)

# "rosetta" or "hy-mt2" - the two families use different instruction shapes,
# and sending one model the other's prompt produces garbage. Inferred from the
# repo name so switching MODEL_REPO alone stays safe; set PROMPT_FORMAT
# explicitly to override.
PROMPT_FORMAT = os.environ.get("PROMPT_FORMAT", "").strip().lower()
if not PROMPT_FORMAT:
    PROMPT_FORMAT = "rosetta" if "rosetta" in MODEL_REPO.lower() else "hy-mt2"

LLAMA_SERVER_HOST = os.environ.get("LLAMA_SERVER_HOST", "127.0.0.1")
LLAMA_SERVER_PORT = _int("LLAMA_SERVER_PORT", 8080)
LLAMA_SERVER_URL = f"http://{LLAMA_SERVER_HOST}:{LLAMA_SERVER_PORT}"

# Sampling defaults per model family: Hy-MT2's model card prescribes
# 0.7/0.6/20/1.05, while Rosetta is a Gemma 3 fine-tune whose card only
# specifies temperature 0.7 - the rest stay at Gemma 3's own defaults.
if PROMPT_FORMAT == "rosetta":
    _TEMPERATURE, _TOP_P, _TOP_K, _REPEAT_PENALTY = 0.7, 0.95, 64, 1.0
else:
    _TEMPERATURE, _TOP_P, _TOP_K, _REPEAT_PENALTY = 0.7, 0.6, 20, 1.05

TEMPERATURE = _float("TEMPERATURE", _TEMPERATURE)
TOP_P = _float("TOP_P", _TOP_P)
TOP_K = _int("TOP_K", _TOP_K)
REPEAT_PENALTY = _float("REPEAT_PENALTY", _REPEAT_PENALTY)
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
