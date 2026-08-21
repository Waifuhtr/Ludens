"""Index the translatable text in an uploaded Ren'Py project.

Accepts either shape people actually have: a zip of nothing but scripts, or a
whole `game/` folder. Both are walked the same way and everything that is not
a script is ignored, so uploading the folder costs no more time than uploading
the scripts alone.

Two directories are always skipped:

  tl/     - somebody else's finished translation. Re-translating a translation
            is the classic way to end up with a game in two languages at once.
  renpy/  - the engine's own source, shipped inside some distributions. Its
            strings belong to Ren'Py, not to the game.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import rpyc, script

SCRIPT_SUFFIXES = (".rpy", ".rpyc")

# Directory names that never hold the game's own translatable script.
_SKIP_DIRS = {"tl", "renpy", "cache", "saves", "lib", "__pycache__"}


@dataclass
class Slot:
    """One place a translation gets written back.

    `start`/`end` bracket the characters between the quotes in the source
    file. A slot from a compiled .rpyc has no writable span - the bytes cannot
    be edited safely - so it is marked unwritable and reaches the game through
    a generated translation file instead.
    """

    file: str
    start: int = -1
    end: int = -1
    quote: str = '"'
    writable: bool = True
    kind: str = "dialogue"


@dataclass
class Unit:
    """One source string and every place it occurs."""

    source: str
    slots: list[Slot] = field(default_factory=list)

    @property
    def occurrences(self) -> int:
        return len(self.slots)


def is_script(path: Path) -> bool:
    return path.suffix.lower() in SCRIPT_SUFFIXES


def is_skipped(relative: Path) -> bool:
    """True when a path sits inside a directory we never read."""
    return any(part.lower() in _SKIP_DIRS for part in relative.parts[:-1])


def iter_scripts(root: Path):
    """Yield every script under `root`, in a stable order.

    A `.rpyc` is only read when it has no `.rpy` sibling. Where both exist,
    Ren'Py itself always treats the `.rpy` as the source of truth and the
    `.rpyc` as a disposable compiled cache, and this tool follows the same
    rule - reading both would translate the same dialogue twice, and shipping
    a `.rpy` we edited next to a `.rpyc` we cannot touch leaves a stale
    compiled tree on disk that no longer matches the source next to it.
    """
    all_paths = {p.relative_to(root) for p in root.rglob("*") if p.is_file()}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or not is_script(path):
            continue
        relative = path.relative_to(root)
        if is_skipped(relative):
            continue
        if path.suffix.lower() == ".rpyc" and relative.with_suffix(".rpy") in all_paths:
            continue
        yield path, relative


def has_scripts(root: Path) -> bool:
    for _ in iter_scripts(root):
        return True
    return False


def extract(root: Path) -> tuple[list[Unit], list[str]]:
    """Read every script under `root`. Returns (units, unreadable_files)."""
    by_source: dict[str, Unit] = {}
    broken: list[str] = []

    def sink(source: str, slot: Slot) -> None:
        unit = by_source.get(source)
        if unit is None:
            unit = Unit(source=source)
            by_source[source] = unit
        unit.slots.append(slot)

    for path, relative in iter_scripts(root):
        name = relative.as_posix()
        if path.suffix.lower() == ".rpy":
            try:
                source = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                try:
                    source = path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    broken.append(name)
                    continue
            try:
                for item in script.find_translatable(source):
                    sink(
                        item.text,
                        Slot(
                            file=name,
                            start=item.start,
                            end=item.end,
                            quote=item.quote,
                            writable=True,
                            kind=item.kind,
                        ),
                    )
            except Exception:  # noqa: BLE001 - one odd script must not stop the scan
                broken.append(name)
            continue

        # Compiled script: readable, not writable.
        try:
            strings = rpyc.extract_strings(path)
        except Exception:  # noqa: BLE001 - unknown or newer .rpyc layout
            broken.append(name)
            continue
        for text, kind in strings:
            sink(text, Slot(file=name, writable=False, kind=kind))

    return list(by_source.values()), broken
