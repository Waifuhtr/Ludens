"""Pull translatable dialogue out of an RPG Maker MV/MZ data folder.

Deliberately narrow. RPG Maker stores executable script, plugin bindings,
asset filenames and engine identifiers in the same JSON arrays as dialogue,
and translating any of those breaks the game rather than mistranslating it -
so this reads exactly four things:

  401 / 405  Show Text / Show Scrolling Text  - the dialogue itself
  102 / 402  Show Choices / When[choice]      - the buttons under that dialogue
  System.json terms                           - the menus wrapped around both
  database name/description/message fields    - items, skills, enemies, states

Everything else is left alone, including the MZ speaker-name field on 101,
name-change commands (320/324/325), plugin commands (356/357) and Script
blocks (355/655).

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

# System.json keys holding player-visible interface text.
#
# `terms` is the menu and options screen: `commands` is New Game / Continue /
# Save / Options, `messages` is the options labels (BGM Volume, Always Dash)
# and the battle log templates, `basic` and `params` are the stat labels.
# The type arrays are shown in the equip and status screens.
#
# Excluded on purpose: `gameTitle` (a proper name, like the character names
# this tool already leaves alone), `currencyUnit` (usually a one-letter symbol
# such as "G" that reads as noise to a translator), and `switches` /
# `variables`, which are developer-facing labels the player never sees.
_SYSTEM_TERM_LISTS = ("basic", "commands", "params")
_SYSTEM_TYPE_LISTS = (
    "armorTypes",
    "elements",
    "equipTypes",
    "skillTypes",
    "weaponTypes",
)

# Database files: flat arrays of entries, index 0 always null (RPG Maker's ids
# are 1-based). Only the fields the player actually reads are listed.
#
# `message1`..`message4` are battle-log templates ("%1 takes damage!") whose %1
# and %2 are filled in by the engine; Hy-MT2 carries them through the same way
# it carries \\C[2], so they are translated like any other line.
#
# Deliberately absent:
#   note      - stores plugin notetags (<tag:value>) mixed with free text.
#               Translating one would silently change plugin behaviour, and
#               splitting text from tags is guesswork, so the whole field is
#               left alone.
#   Actors    - names, nicknames and profiles are the character names this
#               tool does not translate.
#   Classes   - class names read as character labels next to actor names, so
#               they follow the same rule.
_DATABASE_FIELDS: dict[str, tuple[str, ...]] = {
    "Items.json": ("name", "description"),
    "Weapons.json": ("name", "description"),
    "Armors.json": ("name", "description"),
    "Skills.json": ("name", "description", "message1", "message2"),
    "Enemies.json": ("name",),
    "States.json": ("name", "message1", "message2", "message3", "message4"),
}


@dataclass
class Slot:
    """Where one unit's translation gets written back.

    `paths` is a list because a merged run of 401 commands writes one line per
    original command: the box keeps the same number of lines it had.

    `raw` marks a slot that owns a whole field rather than one line of a
    message box. Those are written exactly as the model returned them - a
    two-line item description has to stay two lines, where the line-per-command
    slots get re-flowed to match the box they came from.
    """

    file: str
    paths: list[list] = field(default_factory=list)
    raw: bool = False


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


def _extract_system(data: dict, sink) -> None:
    """Read the player-visible strings out of System.json.

    Entries are frequently null or "" (RPG Maker pads these arrays to a fixed
    length and index 0 is usually blank), so every value is checked before it
    is emitted - writing a translation into a slot the engine expects to be
    empty would put stray text in the menu.
    """
    name = "System.json"

    terms = data.get("terms")
    if isinstance(terms, dict):
        for key in _SYSTEM_TERM_LISTS:
            values = terms.get(key)
            if isinstance(values, list):
                for index, value in enumerate(values):
                    if isinstance(value, str) and value.strip():
                        sink(value, Slot(file=name, paths=[["terms", key, index]], raw=True))

        messages = terms.get("messages")
        if isinstance(messages, dict):
            for key, value in messages.items():
                if isinstance(value, str) and value.strip():
                    sink(value, Slot(file=name, paths=[["terms", "messages", key]], raw=True))

    for key in _SYSTEM_TYPE_LISTS:
        values = data.get(key)
        if isinstance(values, list):
            for index, value in enumerate(values):
                if isinstance(value, str) and value.strip():
                    sink(value, Slot(file=name, paths=[[key, index]], raw=True))


def _extract_database(name: str, data: list, fields: tuple[str, ...], sink) -> None:
    """Read the player-visible fields out of one database file.

    Index 0 of these arrays is null and entries can carry empty strings for
    fields the designer never filled in, so both are skipped: writing a
    translation into a blank description would put text on an item that is
    meant to show none.
    """
    for entry_index, entry in enumerate(data):
        if not isinstance(entry, dict):
            continue
        for key in fields:
            value = entry.get(key)
            if isinstance(value, str) and value.strip():
                sink(
                    value,
                    Slot(file=name, paths=[[entry_index, key]], raw=True),
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

    elif name == "System.json" and isinstance(data, dict):
        _extract_system(data, sink)

    elif name in _DATABASE_FIELDS and isinstance(data, list):
        _extract_database(name, data, _DATABASE_FIELDS[name], sink)


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
