"""Write translations back into the project's JSON, in place and in shape.

Two invariants matter more than translation quality here:

1. A message box keeps the number of command lines it started with. Adding or
   removing entries in an event list shifts every index after it, which breaks
   conditional branches and jump targets. So a translation is re-wrapped into
   exactly the original line count, never more, never fewer.
2. A string is written exactly as the model returned it. Hy-MT2 carries
   control codes through on its own, so there is no post-hoc validation step
   holding translations back.
"""

from __future__ import annotations

import json
from pathlib import Path


def rewrap(text: str, line_count: int) -> list[str]:
    """Fit `text` into exactly `line_count` lines.

    The model is given the box's lines joined by newlines and usually returns
    the same number back, in which case its own breaks are kept. When it does
    not, the text is re-flowed greedily into equal-ish lines so the box still
    looks like a box.
    """
    if line_count <= 1:
        return [text.replace("\n", " ").strip()]

    lines = text.split("\n")
    if len(lines) == line_count:
        return lines

    words = text.replace("\n", " ").split()
    if not words:
        return [""] * line_count

    # Aim for even line lengths rather than filling the first line to the brim.
    target = max(1, len(" ".join(words)) // line_count)
    wrapped: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join(current + [word])
        if current and len(candidate) > target and len(wrapped) < line_count - 1:
            wrapped.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    wrapped.append(" ".join(current))

    while len(wrapped) < line_count:
        wrapped.append("")
    if len(wrapped) > line_count:
        # Never drop text: fold the overflow into the last kept line.
        head = wrapped[: line_count - 1]
        head.append(" ".join(wrapped[line_count - 1 :]))
        wrapped = head
    return wrapped


def _assign(root, path: list, value: str) -> bool:
    """Follow a path of keys/indices and set the final element."""
    node = root
    for step in path[:-1]:
        try:
            node = node[step]
        except (KeyError, IndexError, TypeError):
            return False
    last = path[-1]
    try:
        node[last] = value
    except (KeyError, IndexError, TypeError):
        return False
    return True


def apply(
    data_dir: Path,
    units: list,
    translations: dict[str, str],
) -> tuple[int, int]:
    """Write every validated translation into the JSON files under `data_dir`.

    Groups writes by file so each file is parsed and serialised once, however
    many strings land in it. Returns (written_slots, skipped_slots).
    """
    slots_by_file: dict[str, list[tuple[list[list], str, bool]]] = {}
    for unit in units:
        translated = translations.get(unit.source)
        if translated is None:
            continue
        for slot in unit.slots:
            slots_by_file.setdefault(slot.file, []).append(
                (slot.paths, translated, slot.raw)
            )

    written = skipped = 0
    for file_name, entries in slots_by_file.items():
        json_path = data_dir / file_name
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            skipped += sum(len(paths) for paths, _, _ in entries)
            continue

        for paths, translated, raw in entries:
            # A raw slot is one whole field (an item description, a menu term),
            # so it keeps whatever line breaks the model produced. Everything
            # else is a message box and has to come back with the line count it
            # went in with.
            lines = [translated] if raw else rewrap(translated, len(paths))
            for line, path in zip(lines, paths):
                if _assign(data, path, line):
                    written += 1
                else:
                    skipped += 1

        # ensure_ascii=False keeps Turkish characters readable in the file, and
        # matches how RPG Maker itself writes these (UTF-8, not escaped).
        json_path.write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )

    return written, skipped
