"""Project-wide term dictionary, injected per request.

Character names and game terms have to come out the same way in all 50k
strings, but sending the whole dictionary with every request would blow up
the prompt (and Hy-MT2 weighs every reference pair it is given). So the full
map lives in a JSON file and only the terms that actually occur in the string
being translated are attached.
"""

import json
import re
from pathlib import Path

_TERMS: dict[str, str] = {}
_PATTERNS: list[tuple[re.Pattern[str], str, str]] = []


def _compile(terms: dict[str, str]) -> list[tuple[re.Pattern[str], str, str]]:
    patterns = []
    for source, target in terms.items():
        if not source.strip():
            continue
        # Word boundaries only where the term actually starts/ends with a word
        # character - game terms like "\SE[1]" or "+2 ATK" would never match
        # under an unconditional \b.
        prefix = r"\b" if source[:1].isalnum() else ""
        suffix = r"\b" if source[-1:].isalnum() else ""
        patterns.append(
            (
                re.compile(prefix + re.escape(source) + suffix, re.IGNORECASE),
                source,
                target,
            )
        )
    # Longest first so "Michiru Sato" wins over "Michiru" when both are listed.
    patterns.sort(key=lambda item: len(item[1]), reverse=True)
    return patterns


def load(path: str | None) -> int:
    """Load the term file. Returns how many terms are active."""
    global _TERMS, _PATTERNS
    _TERMS, _PATTERNS = {}, []
    if not path:
        return 0

    file_path = Path(path)
    if not file_path.is_file():
        return 0

    data = json.loads(file_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a JSON object of term -> translation")

    _TERMS = {str(k): str(v) for k, v in data.items()}
    _PATTERNS = _compile(_TERMS)
    return len(_TERMS)


def size() -> int:
    return len(_TERMS)


def match(text: str) -> dict[str, str]:
    """Terms from the loaded file that occur in `text`."""
    if not _PATTERNS:
        return {}
    return {
        source: target
        for pattern, source, target in _PATTERNS
        if pattern.search(text)
    }


def merge_for(text: str, request_glossary: dict[str, str] | None) -> dict[str, str]:
    """Auto-matched terms plus the caller's own, with the caller winning."""
    merged = match(text)
    if request_glossary:
        merged.update(request_glossary)
    return merged
