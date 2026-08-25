"""Find the translatable strings in a .rpy script, with exact source offsets.

Ren'Py scripts mix dialogue with executable Python, asset filenames, style
definitions and screen layout in one file, and the difference between them is
the difference between a translated game and a game that will not start. So
this parser is built to be *certain* about what it touches:

* Every string literal in the file is located in one pass that understands
  comments, escapes and triple quotes. Nothing downstream ever re-scans raw
  text, so a `#` inside dialogue or a quote inside a comment cannot shift an
  offset.
* Statements are classified from a "code view" of each line - the same line
  with the inside of every string blanked out - so a keyword mentioned inside
  dialogue is never mistaken for the statement's own keyword. This only looks
  at bracket-depth-0 text, on purpose: a string sitting inside some other
  call (`action=ShowMenu("save")`) is never mistaken for a label.
* A second, independent pass then finds every string wrapped in `_(...)` or
  `__(...)`, at *any* depth, wherever it sits - inside an `Achievement(...)`
  constructor, a dict three levels deep in a list inside `init python:`.
  `_()` is Ren'Py's own "translate this" marker, so unlike everything else
  here it needs no statement classification: the developer already answered
  the question by writing it. Only a `translate` block's own body is held
  back from this pass, even one that happens to contain a `_()` call.
* Anything not positively recognised as dialogue, a menu choice, screen text
  or `_()`-marked is left alone. Over-skipping costs a line of translation;
  under-skipping corrupts a script.

The offsets are what makes writing back safe: a translation replaces exactly
the characters between one pair of quotes, so no amount of re-flowing by the
model can disturb the code around it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .text import EscapeError, is_translatable, unescape

# Statements whose entire indented body holds no dialogue. Skipping the block
# outright is safer than trusting per-line rules inside it: `style` bodies name
# fonts, `image` bodies name files, `python` bodies are code, and `translate`
# bodies are somebody else's finished translation.
_BLOCK_SKIP = {
    "python",
    "init",
    "style",
    "transform",
    "image",
    "layeredimage",
    "testcase",
    "translate",
    "camera",
}

# Single statements that carry no dialogue. Their arguments are label names,
# asset paths, transitions or expressions.
_LINE_SKIP = {
    "define",
    "default",
    "jump",
    "call",
    "scene",
    "show",
    "hide",
    "with",
    "play",
    "stop",
    "queue",
    "voice",
    "pause",
    "return",
    "pass",
    "window",
    "nvl",
    "use",
    "add",
    "on",
    "key",
    "timer",
    "imagemap",
    "hotspot",
    "hotbar",
    "drag",
    "draggroup",
    "mousearea",
    "imagebutton",
    "input",
    "bar",
    "vbar",
    "viewport",
    "side",
    "grid",
    "vpgrid",
    "fixed",
    "hbox",
    "vbox",
    "frame",
    "null",
    "has",
    "at",
    "audio",
    "sound",
    "music",
    "movie",
    "transclude",
    "default_focus",
}

# Screen statements whose *first* string is shown to the player. The first, not
# the last: `textbutton "OK" action Return()` and
# `text "Hi" style "big"` both put the visible text first and configuration
# after it.
_UI_KEYWORDS = {"text", "textbutton", "tooltip", "caption", "alt", "label"}

# Prefix words allowed in front of a say statement's dialogue, beyond the
# speaker's own name and image attributes.
_SAY_PREFIX_WORDS = {"extend", "nvl"}

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z_0-9.]*$")
_FIRST_WORD_RE = re.compile(r"^([A-Za-z_][A-Za-z_0-9]*)")


@dataclass
class Literal:
    """One string literal, located exactly in the file."""

    start: int          # offset of the first character inside the quotes
    end: int            # offset just past the last character inside the quotes
    quote: str          # the quote character, for re-escaping
    triple: bool
    line: int           # 0-based index of the line the literal opens on
    depth: int          # bracket nesting at the opening quote
    marked: bool         # sits directly inside a `_(...)` / `__(...)` call


@dataclass
class Found:
    """A translatable string plus where to write its translation back."""

    text: str
    start: int
    end: int
    quote: str
    kind: str           # dialogue | menu | ui
    line: int


def _is_underscore_call(source: str, paren_index: int) -> bool:
    """True when the '(' at `paren_index` is `_(` or `__(`.

    Walks back over whitespace, then over one contiguous identifier, and
    compares that whole token - not just the character before the paren - so
    a real name that merely ends in an underscore (`get_text_ (x)`) is never
    mistaken for the marker.
    """
    cursor = paren_index
    while cursor > 0 and source[cursor - 1] in " \t":
        cursor -= 1
    end = cursor
    while cursor > 0 and (source[cursor - 1].isalnum() or source[cursor - 1] == "_"):
        cursor -= 1
    return source[cursor:end] in ("_", "__")


def scan_literals(source: str) -> tuple[list[Literal], list[str]]:
    """Locate every string literal, and build the blanked-out code view.

    Returns the literals and one "code line" per source line: the same text
    with string contents and comments replaced by spaces, so positions still
    line up with the original but no statement rule can be fooled by them.
    """
    literals: list[Literal] = []
    code = list(source)
    # A byte-order mark is not whitespace, so it would glue itself to the
    # first statement's keyword and make line 1 unrecognisable. Blanking it in
    # the code view fixes the classification while leaving the real offsets -
    # and the mark itself - untouched.
    if code and code[0] == "﻿":
        code[0] = " "
    line_index = 0
    depth = 0
    index = 0
    length = len(source)
    # One entry per currently-open '(' ')' pair, tracking whether it was
    # opened by a bare `_` or `__` - Ren'Py's own "translate this" marker.
    # `_("Continue")`, `Achievement(description=_("..."))` and
    # `flavor=_("..."))` inside a dict two calls deep are all reached this way,
    # regardless of what statement or block they sit inside; see `marked` on
    # Literal.
    paren_marks: list[bool] = []

    while index < length:
        char = source[index]

        if char == "\n":
            line_index += 1
            index += 1
            continue

        if char == "#":
            # Comment: blank to end of line. Ren'Py has no block comments.
            while index < length and source[index] != "\n":
                code[index] = " "
                index += 1
            continue

        if char == "(":
            paren_marks.append(_is_underscore_call(source, index))
            depth += 1
            index += 1
            continue
        if char == ")":
            if paren_marks:
                paren_marks.pop()
            depth = max(0, depth - 1)
            index += 1
            continue
        if char in "[{":
            depth += 1
            index += 1
            continue
        if char in "]}":
            depth = max(0, depth - 1)
            index += 1
            continue

        if char not in "\"'":
            index += 1
            continue

        # A string opens here. Triple quotes first, so `"""` is never read as
        # an empty string followed by a stray quote.
        quote = char
        triple = source.startswith(quote * 3, index)
        marker = quote * 3 if triple else quote
        open_line = line_index
        inner_start = index + len(marker)

        cursor = inner_start
        closed = False
        while cursor < length:
            current = source[cursor]
            if current == "\\":
                # Skip the escaped character so an escaped quote cannot close
                # the string. Newlines inside the escape still count for
                # line numbering.
                if cursor + 1 < length:
                    if source[cursor + 1] == "\n":
                        line_index += 1
                    cursor += 2
                    continue
                cursor += 1
                continue
            if current == "\n":
                line_index += 1
                if not triple:
                    # An unterminated single-quoted string: treat the line end
                    # as the end rather than swallowing the rest of the file.
                    break
                cursor += 1
                continue
            if source.startswith(marker, cursor):
                closed = True
                break
            cursor += 1

        inner_end = cursor
        for position in range(inner_start, min(inner_end, length)):
            if code[position] != "\n":
                code[position] = " "

        if closed:
            literals.append(
                Literal(
                    start=inner_start,
                    end=inner_end,
                    quote=quote,
                    triple=triple,
                    line=open_line,
                    depth=depth,
                    marked=bool(paren_marks) and paren_marks[-1],
                )
            )
            index = inner_end + len(marker)
        else:
            index = inner_end

    code_lines = "".join(code).split("\n")
    return literals, code_lines


def _prefix_is_speaker(prefix: str) -> bool:
    """True when the text before a say statement's dialogue is just a speaker.

    A say statement's prefix is the character variable plus any image
    attributes - all bare words. Anything with an operator or a call in it is
    some other statement that happens to contain a string.
    """
    if not prefix:
        return True
    for word in prefix.split():
        if word in _SAY_PREFIX_WORDS:
            continue
        if not _IDENT_RE.match(word):
            return False
    return True


def _line_bounds(source: str) -> list[int]:
    """Start offset of every line, so a line index can address the file."""
    starts = [0]
    for index, char in enumerate(source):
        if char == "\n":
            starts.append(index + 1)
    return starts


def find_translatable(source: str) -> list[Found]:
    """Return every translatable string in one .rpy file."""
    literals, code_lines = scan_literals(source)
    line_starts = _line_bounds(source)

    by_line: dict[int, list[Literal]] = {}
    for literal in literals:
        by_line.setdefault(literal.line, []).append(literal)

    found: list[Found] = []
    skip_indent: int | None = None
    skip_kind: str | None = None
    menu_indent: int | None = None
    continuation = False
    depth = 0
    # Lines that belong to a `translate` block - somebody else's finished
    # translation - so the marked-literal pass below can steer clear of it
    # the same way the main classification does.
    translate_lines: set[int] = set()

    for index, code_line in enumerate(code_lines):
        stripped = code_line.strip()
        line_depth_before = depth
        depth += sum(code_line.count(c) for c in "([{")
        depth -= sum(code_line.count(c) for c in ")]}")
        depth = max(0, depth)

        was_continuation = continuation
        # A statement continues onto the next line while brackets are open or
        # the line ends in a backslash.
        continuation = depth > 0 or code_line.rstrip().endswith("\\")

        if not stripped:
            continue

        indent = len(code_line) - len(code_line.lstrip())

        # A continuation line is part of the statement above it, not a
        # statement of its own - classifying it would read `"Eileen")` from a
        # multi-line Character() call as narration.
        if was_continuation or line_depth_before > 0:
            continue

        if skip_indent is not None:
            if indent > skip_indent:
                if skip_kind == "translate":
                    translate_lines.add(index)
                continue
            skip_indent = None
            skip_kind = None

        if menu_indent is not None and indent <= menu_indent:
            menu_indent = None

        if stripped.startswith("$"):
            continue

        match = _FIRST_WORD_RE.match(stripped)
        first = match.group(1) if match else ""

        if first in _BLOCK_SKIP:
            skip_indent = indent
            skip_kind = first
            if first == "translate":
                translate_lines.add(index)
            continue

        if first == "menu":
            menu_indent = indent
            continue

        if first == "screen":
            # Screens hold player-visible text, so only the header is skipped.
            continue

        candidates = [lit for lit in by_line.get(index, []) if lit.depth == 0]
        if not candidates:
            continue

        # `label` is two different statements: `label start:` is a script
        # label, `label "Text"` inside a screen is a caption.
        if first == "label" and not stripped[len("label"):].lstrip().startswith(
            ("'", '"')
        ):
            continue

        if first in _UI_KEYWORDS:
            chosen = candidates[0]
            kind = "ui"
        elif first in _LINE_SKIP:
            continue
        else:
            # Everything before the opening quote of the first string. The
            # quote itself is excluded - it is not part of the speaker.
            opening = candidates[0].start - (3 if candidates[0].triple else 1)
            prefix = code_line[: opening - line_starts[index]].strip()
            # An assignment that escaped the `$` and define checks is not
            # dialogue, whatever it looks like.
            if "=" in prefix:
                continue
            if not _prefix_is_speaker(prefix):
                continue
            # With two strings and no prefix the line is `"Speaker" "text"`,
            # so the dialogue is the last one either way.
            chosen = candidates[-1]
            kind = "menu" if menu_indent is not None and not prefix else "dialogue"

        item = _literal_to_found(source, chosen, kind, index + 1)
        if item is not None:
            found.append(item)

    # `_()` / `__()` is Ren'Py's own "translate this" marker, and it means
    # exactly that wherever it appears - inside a `python:`/`init python:`
    # block, an `Achievement(...)` constructor, a dict buried in a list two
    # levels deep. The scan above only classifies statements at bracket-depth
    # 0 (so a style name or an action sitting next to a label is never
    # mistaken for one), which is also why it cannot see into any of those
    # places. This second pass doesn't classify anything; the developer
    # already did, explicitly, by writing `_(...)`. Depth-0 literals can never
    # be marked (marking requires an open paren), so this cannot re-find
    # anything the loop above already collected.
    seen = {(f.start, f.end) for f in found}
    for literal in literals:
        if not literal.marked or literal.line in translate_lines:
            continue
        if (literal.start, literal.end) in seen:
            continue
        item = _literal_to_found(source, literal, "ui", literal.line + 1)
        if item is not None:
            found.append(item)

    return found


def _literal_to_found(source: str, literal: Literal, kind: str, line: int) -> Found | None:
    raw = source[literal.start : literal.end]
    try:
        value = unescape(raw)
    except EscapeError:
        # An escape this tool will not round-trip. Leaving the line in the
        # source untranslated is always recoverable; writing back a guess is
        # not.
        return None
    if not value.strip() or not is_translatable(value):
        return None
    if literal.triple:
        # Triple-quoted bodies are found and skipped rather than translated:
        # their content is re-indented by Ren'Py and a rewritten body would
        # change the layout it depends on.
        return None
    return Found(
        text=value,
        start=literal.start,
        end=literal.end,
        quote=literal.quote,
        kind=kind,
        line=line,
    )
