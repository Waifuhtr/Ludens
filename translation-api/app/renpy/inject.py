"""Write translations back into .rpy scripts.

A translation replaces exactly the characters between one pair of quotes and
nothing else. Spans are applied from the end of the file backwards so that
every offset still refers to the text it was measured against - rewriting
front-to-back would shift each following span by the length the last one
changed.

The script around the strings is never re-indented, re-wrapped or re-parsed, so
a file whose strings all translate to themselves comes back byte-identical.
"""

from __future__ import annotations

from pathlib import Path

from .text import escape


def apply_to_source(source: str, spans: list[tuple[int, int, str, str]]) -> str:
    """Replace each (start, end, quote, translation) span in `source`."""
    ordered = sorted(spans, key=lambda item: item[0], reverse=True)
    out = source
    last_start = len(source) + 1
    for start, end, quote, translated in ordered:
        if end > last_start:
            # Overlapping spans would corrupt the file. The scanner cannot
            # produce them, but a stale units.json against an edited source
            # could, so refuse rather than write nonsense.
            raise ValueError(f"overlapping span at {start}:{end}")
        out = out[:start] + escape(translated, quote) + out[end:]
        last_start = start
    return out


def apply(project_dir: Path, units: list, translations: dict[str, str]) -> tuple[int, int]:
    """Write every translated unit into the scripts under `project_dir`.

    Groups by file so each script is read and written once. Returns
    (written_spans, skipped_spans).
    """
    by_file: dict[str, list[tuple[int, int, str, str]]] = {}
    for unit in units:
        translated = translations.get(unit.source)
        if translated is None:
            continue
        for slot in unit.slots:
            if not slot.writable:
                continue
            by_file.setdefault(slot.file, []).append(
                (slot.start, slot.end, slot.quote, translated)
            )

    written = skipped = 0
    for name, spans in by_file.items():
        path = project_dir / name
        try:
            source = path.read_text(encoding="utf-8")
        except OSError:
            skipped += len(spans)
            continue
        try:
            updated = apply_to_source(source, spans)
        except ValueError:
            skipped += len(spans)
            continue
        path.write_text(updated, encoding="utf-8")
        written += len(spans)

    return written, skipped
