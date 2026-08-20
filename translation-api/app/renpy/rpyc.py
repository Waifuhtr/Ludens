"""Read the dialogue out of a compiled .rpyc script.

A .rpyc holds Ren'Py's parsed syntax tree, pickled and deflated. That is
enough to *read* every line of dialogue, which is what makes it possible to
translate a game that ships without its .rpy sources. It is not enough to write
one back: the tree also encodes line numbers and file offsets that the engine
checks, so translated text reaches these games through a generated translation
file instead of an edit.

Unpickling a file from a stranger normally means running their code - the
pickle format can name any importable object and call it. This reader never
imports anything the file asks for. Every class name it encounters is answered
with an inert stand-in that only records the attributes assigned to it, so a
malicious .rpyc has nothing to reach for.
"""

from __future__ import annotations

import io
import pickle
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

_MAX_NODES = 2_000_000


class _Stand:
    """Inert stand-in for a class named inside the pickle."""

    __slots__ = ("__dict__",)

    def __init__(self, *args, **kwargs) -> None:
        # Ren'Py reconstructs most nodes through __setstate__, but a few are
        # built with positional arguments; keeping them lets the walker still
        # see any strings they carry.
        if args:
            self.__dict__["_args"] = args

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


def _load_tree(path: Path):
    blob = path.read_bytes()
    if blob.startswith(_MAGIC):
        slots = _slots(blob)
        # Slot 1 carries the syntax tree in every version that uses this
        # container; the others hold source and metadata.
        payload = slots.get(1)
        if payload is None:
            raise ValueError("no syntax-tree slot in .rpyc")
        data = zlib.decompress(payload)
    else:
        # Ren'Py 6.17 and older: the whole file is one deflated pickle.
        data = zlib.decompress(blob)
    return _SafeUnpickler(io.BytesIO(data)).load()


def _walk(node, sink, seen: set[int], budget: list[int]) -> None:
    """Collect dialogue from the object graph, depth first."""
    if budget[0] <= 0:
        return
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
        if isinstance(what, str):
            sink(what, "dialogue")

    elif kind in _MENU_NODES:
        items = fields.get("items")
        if isinstance(items, (list, tuple)):
            for item in items:
                if isinstance(item, (list, tuple)) and item and isinstance(item[0], str):
                    sink(item[0], "menu")

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
