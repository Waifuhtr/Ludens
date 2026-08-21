"""Read the player-visible text out of a compiled .rpyc script.

A .rpyc holds Ren'Py's parsed syntax tree, pickled and deflated. Mobile builds
routinely ship without any .rpy sources, so this is the only way to reach
their text at all - it is a first-class path here, not a fallback.

Two kinds of text come out, and they are found very differently:

* **Dialogue and menu choices** are stored in the tree as plain strings. Say
  text is never evaluated as code, only substituted (`[var]`) at display time,
  so `Say.what` and a `Menu` item's label can simply be read.

* **Screen text** - `text`, `textbutton`, `label`, `tooltip` inside a `screen`
  block - is not stored as a string at all. Ren'Py compiles *every* screen
  argument, including a plain `"Continue"`, into a `PyExpr` holding Python
  source, and the label sits in exactly the same position as a style name, an
  action or a variable. So a label cannot be recognised by position; it has to
  be recognised by *shape*. Each argument's source is parsed and accepted only
  when it is a bare string literal or an explicit `_()` / `__()` translation
  marker - never a name, attribute or call. That is what keeps
  `Preference("text speed")`, `gui.main_menu_background`, `i.caption` and
  `SideImage()` out, while letting `_("Options")` and `"Fonlar: [fon]"`
  through.

  Two traps are worth naming, because both are real strings that look
  translatable and are not. `key "K_F5"` puts a keysym in the same slot a
  label would occupy - excluded because a `key` statement has no text style.
  And Ren'Py's own help screen writes its key names as bare `"H"` / `"Shift+A"`
  while wrapping every description beside them in `_()`; translating a key
  name renames a control the player then cannot find.

It is not enough to write a translation back into the .rpyc: the tree also
encodes line numbers and file offsets that the engine checks, so translated
text reaches these games through a generated translation file instead of an
edit - see `tl.py`.

Unpickling a file from a stranger normally means running their code - the
pickle format can name any importable object and call it. This reader never
imports anything the file asks for. Every class name it encounters is answered
with an inert stand-in that only records the attributes assigned to it, so a
malicious .rpyc has nothing to reach for.
"""

from __future__ import annotations

import ast
import io
import pickle
import re
import struct
import zlib
from pathlib import Path

_MAGIC = b"RENPY RPC2"

# Node types whose text the player reads.
_SAY_NODES = {"Say"}
_MENU_NODES = {"Menu"}
# Existing translations inside the compiled file - skipping them keeps a
# part-translated game from being translated a second time.
_TRANSLATE_NODES = {"Translate", "TranslateString", "TranslateBlock", "TranslatePython"}

# Screen-language nodes carrying player-visible text.
#
# `SLDisplayable.style` names the *built-in* style of the widget, which is set
# by which statement created it and is not changed by a `style "foo"` keyword
# override. That makes it a reliable statement identifier:
#
#     text "..."        -> style "text"
#     textbutton "..."  -> style "button"
#     label "..."       -> style "label"
#
# Everything else is deliberately excluded, and the exclusions matter as much
# as the inclusions: `key "K_F5"`, `add gui.main_menu_background` and
# `imagebutton auto="..."` all carry string arguments that are keysyms, asset
# names or style prefixes rather than text, and they arrive with a style of
# None or one not listed here.
_TEXT_STYLES = {"text", "button", "label"}

# Keyword arguments that hold text rather than configuration. Kept to the two
# Ren'Py documents as player-facing; `action`, `style`, `value` and `hovered`
# routinely hold string literals that are code or style names.
_TEXT_KEYWORDS = {"tooltip", "alt"}

_SL_DISPLAYABLE_NODES = {"SLDisplayable"}
_SL_USE_NODES = {"SLUse"}

# Bare (not `_()`-wrapped) literals matching these are input bindings, not
# prose. Ren'Py's own help screen is the reason this exists: it writes the key
# names as plain strings - "H", "S", "Shift+A" - while wrapping every
# description beside them in `_()`. Translating a key name renames a control
# the player then cannot find.
# Ren'Py's disambiguation tag: `{#auto_page}A` displays as just "A", the tag
# existing only to keep two otherwise identical strings apart in a translation
# file. It has to stay in the key verbatim, but it must not hide a one-letter
# control label from the shortcut check above.
_DISAMBIGUATION_RE = re.compile(r"\{#[^}]*\}")

_SHORTCUT_RE = re.compile(
    r"""^(?:
        [A-Za-z0-9]                                   # one key: H, S, 1
      | K_[A-Za-z0-9_]+                               # Ren'Py keysym: K_F5
      | F\d{1,2}                                      # F1 .. F12
      | (?:Shift|Ctrl|Control|Alt|Cmd|Meta|Super)     # modifier combinations
        (?:\s*\+\s*[A-Za-z0-9_]+)+
      | (?:mouse|joy|pad)_[A-Za-z0-9_]+               # input device ids
    )$""",
    re.VERBOSE,
)

# Depth-first node budget. Real scripts need a few AST objects per line of
# dialogue, so a script with tens of thousands of lines stays orders of
# magnitude under this - it exists to bound a pathological or corrupted file,
# not real games. If it is ever exhausted, the file is reported as unreadable
# rather than silently returning a partial scan: a game that is missing lines
# with no warning is worse than one flagged for a manual look.
_MAX_NODES = 2_000_000


class BudgetExceeded(Exception):
    """The node walk hit `_MAX_NODES` - the file may not be fully read."""


class _Stand:
    """Inert stand-in for a class named inside the pickle."""

    __slots__ = ("__dict__",)

    def __new__(cls, *args, **kwargs):
        # Overridden (rather than relying on the default object.__new__)
        # specifically so positional constructor arguments are captured no
        # matter which pickle opcode built this object - NEWOBJ reconstructs
        # via __new__ alone and never calls __init__.
        self = object.__new__(cls)
        if args:
            self.__dict__["_args"] = args
        return self

    def __init__(self, *args, **kwargs) -> None:
        pass

    def __setstate__(self, state) -> None:
        if isinstance(state, dict):
            self.__dict__.update(state)
        else:
            self.__dict__["_state"] = state

    # Pickle sometimes appends to or updates a reconstructed object.
    def append(self, item) -> None:
        self.__dict__.setdefault("_items", []).append(item)

    def extend(self, items) -> None:
        self.__dict__.setdefault("_items", []).extend(items)

    def __setitem__(self, key, value) -> None:
        self.__dict__.setdefault("_map", {})[key] = value


_stand_cache: dict[tuple[str, str], type] = {}


def _stand_for(module: str, name: str) -> type:
    key = (module, name)
    cached = _stand_cache.get(key)
    if cached is None:
        cached = type(name, (_Stand,), {"__module__": module})
        _stand_cache[key] = cached
    return cached


class _SafeUnpickler(pickle.Unpickler):
    """Unpickler that resolves every name to an inert stand-in."""

    def find_class(self, module: str, name: str):
        return _stand_for(module, name)

    def persistent_load(self, pid):
        return None


def _expr_source(node) -> str | None:
    """The Python source behind a compiled screen argument.

    Ren'Py stores every screen-language argument as a PyExpr - a str subclass
    carrying the expression's source plus its origin. Reconstructed through the
    inert stand-in above, that source is the first constructor argument.
    """
    if type(node).__name__ != "PyExpr":
        return None
    args = getattr(node, "__dict__", {}).get("_args")
    if args and isinstance(args[0], str):
        return args[0]
    return None


def _literal_from_expr(source: str) -> tuple[str, bool] | None:
    """Pull a translatable literal out of one screen argument.

    Returns `(text, explicitly_marked)`, or None when the argument is anything
    other than a plain string. This is the whole safety story for screen text:
    a screen argument is an arbitrary Python expression, and `title`,
    `i.caption`, `SideImage()` and `Preference("text speed")` all sit in the
    same position as the label the player reads. Parsing the source and
    accepting only a literal - never a name, attribute or call - is what keeps
    a style name or an action from being handed to a translator.

    `explicitly_marked` is True for `_("...")` and `__("...")`, Ren'Py's own
    "this string is shown to a human" marker. It is the difference between a
    caption and a keysym in Ren'Py's own screens, so callers hold bare literals
    to a stricter standard.
    """
    try:
        parsed = ast.parse(source.strip(), mode="eval").body
    except (SyntaxError, ValueError, MemoryError, RecursionError):
        return None

    if isinstance(parsed, ast.Constant) and isinstance(parsed.value, str):
        return parsed.value, False

    if (
        isinstance(parsed, ast.Call)
        and isinstance(parsed.func, ast.Name)
        and parsed.func.id in ("_", "__")
        and len(parsed.args) == 1
        and not parsed.keywords
        and isinstance(parsed.args[0], ast.Constant)
        and isinstance(parsed.args[0].value, str)
    ):
        return parsed.args[0].value, True

    return None


def _screen_text(node, sink) -> None:
    """Collect the player-visible strings from one screen-language node."""
    fields = node.__dict__
    kind = type(node).__name__

    if kind in _SL_DISPLAYABLE_NODES:
        if fields.get("style") in _TEXT_STYLES:
            positional = fields.get("positional")
            if isinstance(positional, (list, tuple)) and positional:
                # The visible text is always the first positional argument;
                # anything after it is configuration.
                source = _expr_source(positional[0])
                if source is not None:
                    _emit_literal(source, sink)

        for entry in fields.get("keyword") or ():
            if not isinstance(entry, (list, tuple)) or len(entry) != 2:
                continue
            name, value = entry
            if name in _TEXT_KEYWORDS:
                source = _expr_source(value)
                if source is not None:
                    _emit_literal(source, sink)

    elif kind in _SL_USE_NODES:
        # `use game_menu(_("Options"))` - a screen's title is passed in rather
        # than written inside it. Only positional arguments are read, and only
        # explicitly marked ones: a bare literal in this position is far more
        # often a configuration value (`scroll="viewport"`) than a caption.
        args = getattr(fields.get("args"), "__dict__", {}).get("arguments")
        for entry in args or ():
            if not isinstance(entry, (list, tuple)) or len(entry) != 2:
                continue
            name, value = entry
            if name is not None:
                continue
            source = _expr_source(value)
            if source is None:
                continue
            found = _literal_from_expr(source)
            if found and found[1]:
                sink(found[0], "ui")


def _emit_literal(source: str, sink) -> None:
    found = _literal_from_expr(source)
    if found is None:
        return
    text, explicit = found
    visible = _DISAMBIGUATION_RE.sub("", text).strip()

    # A label whose whole visible content is one character is a glyph, not
    # prose - the "A" and "Q" on Ren'Py's auto-page and quick-page buttons.
    # These carry a disambiguation tag precisely *because* a bare "A" is
    # meaningless to a translator, and they sit in fixed-width square buttons.
    # There is nothing to gain by translating one and a layout to lose if the
    # model answers with a word, so they are skipped even when explicitly
    # marked with _().
    if len(visible) <= 1:
        return

    if not explicit and _SHORTCUT_RE.match(visible):
        return

    sink(text, "ui")


def _slots(blob: bytes) -> dict[int, bytes]:
    """Split an RPC2 container into its numbered slots."""
    slots: dict[int, bytes] = {}
    cursor = len(_MAGIC)
    while cursor + 12 <= len(blob):
        number, start, length = struct.unpack("<III", blob[cursor : cursor + 12])
        cursor += 12
        if number == 0:
            break
        if start + length > len(blob):
            raise ValueError("slot runs past end of file")
        slots[number] = blob[start : start + length]
    return slots


def _inflate(payload: bytes) -> bytes:
    try:
        return zlib.decompress(payload)
    except zlib.error:
        # Every RPC2 slot shipped by every Ren'Py release so far is deflated,
        # but the fallback costs nothing and means a future format change
        # degrades to "read the raw pickle" instead of an outright failure.
        return payload


def _load_tree(path: Path):
    blob = path.read_bytes()
    if blob.startswith(_MAGIC):
        slots = _slots(blob)
        # Slot 1 carries the syntax tree in every version that uses this
        # container; the others hold source and metadata.
        payload = slots.get(1)
        if payload is None:
            raise ValueError("no syntax-tree slot in .rpyc")
        data = _inflate(payload)
    else:
        # Ren'Py 6.17 and older: the whole file is one deflated pickle.
        data = _inflate(blob)
    return _SafeUnpickler(io.BytesIO(data)).load()


def _walk(node, sink, seen: set[int], budget: list[int]) -> None:
    """Collect dialogue from the object graph, depth first."""
    if budget[0] <= 0:
        raise BudgetExceeded
    budget[0] -= 1

    if isinstance(node, (str, bytes, int, float, bool, type(None))):
        return

    marker = id(node)
    if marker in seen:
        return
    seen.add(marker)

    if isinstance(node, dict):
        for value in node.values():
            _walk(value, sink, seen, budget)
        return
    if isinstance(node, (list, tuple, set, frozenset)):
        for value in node:
            _walk(value, sink, seen, budget)
        return

    fields = getattr(node, "__dict__", None)
    if not isinstance(fields, dict):
        return

    kind = type(node).__name__

    if kind in _TRANSLATE_NODES:
        # The body of a translate node *is* an existing translation. Reading it
        # would feed a finished translation back through the model, so the
        # whole subtree is left unread - the untranslated original is still in
        # the script as an ordinary Say node.
        return

    if kind in _SAY_NODES:
        what = fields.get("what")
        if isinstance(what, bytes):
            what = what.decode("utf-8", errors="replace")
        if isinstance(what, str):
            sink(what, "dialogue")

    elif kind in _MENU_NODES:
        items = fields.get("items")
        if isinstance(items, (list, tuple)):
            for item in items:
                if not isinstance(item, (list, tuple)) or not item:
                    continue
                label = item[0]
                if isinstance(label, bytes):
                    label = label.decode("utf-8", errors="replace")
                if isinstance(label, str):
                    sink(label, "menu")

    elif kind in _SL_DISPLAYABLE_NODES or kind in _SL_USE_NODES:
        _screen_text(node, sink)

    for value in fields.values():
        _walk(value, sink, seen, budget)


def extract_strings(path: Path) -> list[tuple[str, str]]:
    """Return (text, kind) for every readable line of dialogue in a .rpyc."""
    tree = _load_tree(path)
    out: list[tuple[str, str]] = []
    seen_text: set[str] = set()

    def sink(text: str, kind: str) -> None:
        if not text.strip() or text in seen_text:
            return
        from .text import is_translatable

        if not is_translatable(text):
            return
        seen_text.add(text)
        out.append((text, kind))

    _walk(tree, sink, set(), [_MAX_NODES])
    return out
