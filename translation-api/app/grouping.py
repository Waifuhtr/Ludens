"""Pack several strings into one generation and unpack the result.

Translating 50k game strings one request at a time pays the instruction
prompt's cost once per string and gives the model no idea what came before,
which is where pronoun/name drift in dialogue comes from. Sending a numbered
group instead amortises the instruction and lets the model see the
surrounding lines.

The risk is the model dropping, merging or renumbering a segment, so decoding
is strict: anything that does not come back with exactly the expected markers
is rejected and the caller re-translates that group one string at a time.
"""

import re

# Marker wrapping the segment index. Deliberately not a bracket form that
# collides with RPG Maker control codes (\V[1], \N[1], %1): the model has to
# copy these through untouched, and reusing the game's own syntax invites it
# to treat them as translatable content.
_MARKER = "<<{n}>>"
_MARKER_RE = re.compile(r"^[ \t]*<<\s*(\d+)\s*>>[ \t]?", re.MULTILINE)


def encode(texts: list[str]) -> str:
    """Render texts as a numbered list, one marker per segment."""
    return "\n".join(
        f"{_MARKER.format(n=i)} {text}" for i, text in enumerate(texts, start=1)
    )


def decode(output: str, expected: int) -> list[str] | None:
    """Split a grouped translation back into segments.

    Returns None when the output does not carry exactly the markers 1..expected
    once each - that is the signal to fall back to per-string translation
    rather than silently returning misaligned text.
    """
    matches = list(_MARKER_RE.finditer(output))
    if len(matches) != expected:
        return None

    segments: list[str] = []
    for index, match in enumerate(matches):
        if int(match.group(1)) != index + 1:
            return None
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(output)
        segments.append(output[start:end].strip("\n"))

    if any(not segment.strip() for segment in segments):
        return None
    return segments


def chunk(texts: list[str], size: int) -> list[list[str]]:
    """Split texts into consecutive groups, preserving order."""
    if size <= 1:
        return [[text] for text in texts]
    return [texts[i : i + size] for i in range(0, len(texts), size)]
