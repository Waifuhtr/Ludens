"""Ren'Py string-literal handling.

Two jobs, both of which have to be exactly reversible or the game stops
compiling:

1. Turning the characters between the quotes in a .rpy file into the text a
   translator should see, and back again.
2. Deciding whether a string carries any language at all, so pure markup like
   "{i}[player]{/i}" never costs a generation.

Ren'Py's own text syntax matters here. `{...}` is a text tag, `[...]` is a
variable interpolation, and both are doubled (`{{`, `[[`) to mean a literal
brace or bracket. Those doubles must survive untouched: turning `[[` into `[`
would change what the player sees, and turning it into a variable reference
would crash the game on a missing name.
"""

from __future__ import annotations

import re

# The escape sequences this module round-trips. Deliberately short: every
# sequence here is unescaped on the way in and re-escaped identically on the
# way out, so a string that is never translated comes back byte-for-byte.
#
# A string containing any *other* backslash escape (Ren'Py's `\ ` hard space is
# the one that shows up in practice) is refused by `unescape` rather than
# guessed at - see `is_safe_literal`. Those strings are left in the source
# untranslated, which costs a line of dialogue but can never corrupt a script.
_UNESCAPE = {
    "\\": "\\",
    '"': '"',
    "'": "'",
    "n": "\n",
    "t": "\t",
}
_ESCAPE = {
    "\\": "\\\\",
    "\n": "\\n",
    "\t": "\\t",
}

_ESCAPE_RE = re.compile(r"\\(.)", re.DOTALL)

# Text tags and interpolations, with the doubled literal forms matched first so
# `{{` is never mistaken for the start of a tag.
_MARKUP_RE = re.compile(
    r"\{\{|\[\[|\{[^{}]*\}|\[[^\[\]]*\]"
)


class EscapeError(ValueError):
    """Raised for a literal using an escape this module will not round-trip."""


def is_safe_literal(raw: str) -> bool:
    """True when `raw` (the characters between the quotes) round-trips."""
    try:
        unescape(raw)
    except EscapeError:
        return False
    return True


def unescape(raw: str) -> str:
    """Turn the source characters between quotes into the readable text.

    Raises EscapeError on an escape sequence outside the supported set, so the
    caller can leave that literal alone instead of writing back something that
    means something different.
    """
    out: list[str] = []
    index = 0
    length = len(raw)
    while index < length:
        char = raw[index]
        if char != "\\":
            out.append(char)
            index += 1
            continue
        if index + 1 >= length:
            raise EscapeError("literal ends on a lone backslash")
        nxt = raw[index + 1]
        if nxt not in _UNESCAPE:
            raise EscapeError(f"unsupported escape \\{nxt}")
        out.append(_UNESCAPE[nxt])
        index += 2
    return "".join(out)


def escape(text: str, quote: str) -> str:
    """Render `text` back into the characters that belong between `quote`s.

    Only the enclosing quote is escaped: a single quote inside a double-quoted
    string is left bare, exactly as Ren'Py writes it.
    """
    out: list[str] = []
    for char in text:
        if char in _ESCAPE:
            out.append(_ESCAPE[char])
        elif char == quote:
            out.append("\\" + char)
        else:
            out.append(char)
    return "".join(out)


def strip_markup(text: str) -> str:
    """Remove text tags and interpolations, keeping the words between them."""
    return _MARKUP_RE.sub(" ", text)


def is_translatable(text: str) -> bool:
    """False for strings that are only markup, numbers or punctuation.

    A screen is full of these - "{i}{/i}", "[points]", "- - -" - and each one
    sent to the model costs a full generation and invites it to invent words
    that were never in the source.
    """
    return any(char.isalpha() for char in strip_markup(text))
