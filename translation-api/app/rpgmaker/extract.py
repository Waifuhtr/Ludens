"""Pull translatable dialogue out of an RPG Maker MV/MZ data folder.

Deliberately narrow. RPG Maker stores executable script, plugin bindings,
asset filenames and engine identifiers in the same JSON arrays as dialogue,
and translating any of those breaks the game rather than mistranslating it -
so this reads exactly two things:

  401 / 405  Show Text / Show Scrolling Text  - the dialogue itself
  102 / 402  Show Choices / When[choice]      - the buttons under that dialogue

Everything else is left alone, including the database files (item and skill
names), System.json terms, the MZ speaker-name field on 101, name-change
commands (320/324/325), plugin commands (356/357) and Script blocks
(355/655).

Consecutive 401 commands are one message box split across lines, not separate
sentences, so a run of them is merged into a single unit and translated as one
piece of text - translating "I've been waiting for you" and "for a while."
independently produces two unrelated fragments.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

# Event command codes we read. Anything not listed here is skipped.
CODE_TEXT = 401          # Show Text body line
CODE_SCROLL_TEXT = 405   # Show Scrolling Text body line
CODE_CHOICES = 102       # Show Choices (parameters[0] is a list of labels)
CODE_WHEN_CHOICE = 402   # When [choice] (parameters[1] repeats the label)

# Files that never contain event lists; skipped before parsing.
_SKIP_FILES = {"Tilesets.json", "Animations.json", "MapInfos.json"}


@dataclass
class Slot:
    """Where one unit's translation gets written back.

    `paths` is a list because a merged run of 401 commands writes one line per
    original command: the box keeps the same number of lines it had.
    """

    file: str
    paths: list[list] = field(default_factory=list)


@dataclass
class Unit:
    """One source string plus every place it occurs.

    Units are keyed by source text across the whole project, so a line like
    "Yes" that appears in 300 events is translated once and written 300 times.
    In a full game this is the difference between tens of thousands of
    generations and a few thousand.
    """

    source: str
    slots: list[Slot] = field(default_factory=list)

    @property
    def occurrences(self) -> int:
        return len(self.slots)


def _walk_event_list(commands: list, base_path: list, file_name: str, sink) -> None:
    """Scan one event command list, emitting (source, Slot) pairs to `sink`."""
    index = 0
    while index < len(commands):
        command = commands[index]
        if not isinstance(command, dict):
            index += 1
            continue

        code = command.get("code")
        params = command.get("parameters")

        if code in (CODE_TEXT, CODE_SCROLL_TEXT):
            # Gather the whole run of same-code commands: one message box.
            run_paths: list[list] = []
            run_lines: list[str] = []
            while index < len(commands):
                nxt = commands[index]
                if (
                    not isinstance(nxt, dict)
                    or nxt.get("code") != code
                    or not isinstance(nxt.get("parameters"), list)
                    or not nxt["parameters"]
                    or not isinstance(nxt["parameters"][0], str)
                ):
                    break
                run_paths.append(base_path + [index, "parameters", 0])
                run_lines.append(nxt["parameters"][0])
                index += 1
            if run_paths:
                sink("\n".join(run_lines), Slot(file=file_name, paths=run_paths))
            continue

        if code == CODE_CHOICES and isinstance(params, list) and params:
            labels = params[0]
            if isinstance(labels, list):
                for label_index, label in enumerate(labels):
                    if isinstance(label, str) and label.strip():
                        sink(
                            label,
                            Slot(
                                file=file_name,
                                paths=[base_path + [index, "parameters", 0, label_index]],
                            ),
                        )

        elif code == CODE_WHEN_CHOICE and isinstance(params, list) and len(params) > 1:
            # Mirrors the 102 label. Emitted separately, but because units are
            # keyed by source text both copies land on the same translation and
            # stay in sync automatically.
            if isinstance(params[1], str) and params[1].strip():
                sink(
                    params[1],
                    Slot(file=file_name, paths=[base_path + [index, "parameters", 1]]),
                )

        index += 1


def _walk_pages(container: dict, base_path: list, file_name: str, sink) -> None:
    """Events hold their commands under pages[].list; troops do the same."""
    pages = container.get("pages")
    if not isinstance(pages, list):
        return
    for page_index, page in enumerate(pages):
        if isinstance(page, dict) and isinstance(page.get("list"), list):
            _walk_event_list(
                page["list"], base_path + ["pages", page_index, "list"], file_name, sink
            )


def _extract_file(name: str, data, sink) -> None:
    if name.startswith("Map") and isinstance(data, dict):
        # Map001.json ... events[] -> pages[] -> list[]
        events = data.get("events")
        if isinstance(events, list):
            for event_index, event in enumerate(events):
                if isinstance(event, dict):
                    _walk_pages(event, ["events", event_index], name, sink)

    elif name == "CommonEvents.json" and isinstance(data, list):
        # Flat array of events, each with its own list[] (no pages).
        for event_index, event in enumerate(data):
            if isinstance(event, dict) and isinstance(event.get("list"), list):
                _walk_event_list(event["list"], [event_index, "list"], name, sink)

    elif name == "Troops.json" and isinstance(data, list):
        # Battle events, shaped like map events.
        for troop_index, troop in enumerate(data):
            if isinstance(troop, dict):
                _walk_pages(troop, [troop_index], name, sink)


def detect_data_root(root: Path) -> tuple[Path, str] | None:
    """Locate the data folder in an unpacked upload.

    MV keeps it at www/data, MZ at data, and people zip projects from
    inconsistent depths - so search rather than assume. Returns the folder and
    the engine label, or None when nothing looks like an RPG Maker project.
    """
    candidates: list[tuple[Path, str]] = []
    for path in [root, *root.rglob("*")]:
        if not path.is_dir():
            continue
        if path.name == "data":
            engine = "mv" if path.parent.name == "www" else "mz"
            candidates.append((path, engine))

    for data_dir, engine in sorted(candidates, key=lambda item: len(item[0].parts)):
        # A real data folder has the database files, not just a stray "data".
        names = {p.name for p in data_dir.glob("*.json")}
        if "System.json" in names or any(n.startswith("Map") for n in names):
            return data_dir, engine
    return None


def extract(data_dir: Path) -> tuple[list[Unit], list[str]]:
    """Read every event file. Returns (units, skipped_files_with_errors)."""
    by_source: dict[str, Unit] = {}
    broken: list[str] = []

    def sink(source: str, slot: Slot) -> None:
        if not source.strip():
            return
        unit = by_source.get(source)
        if unit is None:
            unit = Unit(source=source)
            by_source[source] = unit
        unit.slots.append(slot)

    for json_path in sorted(data_dir.glob("*.json")):
        if json_path.name in _SKIP_FILES:
            continue
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            broken.append(json_path.name)
            continue
        _extract_file(json_path.name, data, sink)

    return list(by_source.values()), broken
