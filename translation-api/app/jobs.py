"""The single background translation run, shared by every game engine.

One job at a time, for the whole process. There is a single GPU behind this, so
a second concurrent project would only make both finish later while doubling
VRAM pressure - and that has to hold *across* engines, not just within one.
A Ren'Py job and an RPG Maker job compete for exactly the same slots, so they
share one runner and one lock.

The run is restart-safe. Every finished string is written to translations.json,
and on startup a project still marked `translating` is picked back up: it
re-reads what is already done and works through the remainder, so a Space that
sleeps mid-game resumes instead of paying for the whole run again.
"""

from __future__ import annotations

import asyncio
import time
from typing import Callable

from . import config, glossary as glossary_store, llama_client
from .translation import build_messages

# How often progress reaches disk. Small enough that a crash loses seconds of
# GPU time, large enough not to rewrite a growing JSON file per string.
_FLUSH_EVERY = 25

RPGM = "rpgm"
RENPY = "renpy"

_task: asyncio.Task | None = None
_cancel = False
_active_id: str | None = None
_active_kind: str | None = None


def _engine(kind: str) -> tuple[object, Callable[[str], bool]]:
    """Resolve a project kind to its store and its translatability test.

    Imported lazily: the stores import config, and importing them at module
    scope would tie this module's import order to theirs.
    """
    if kind == RENPY:
        from .renpy import store
        from .renpy.text import is_translatable
    else:
        from .rpgmaker import store
        from .translation import is_translatable
    return store, is_translatable


def stores() -> list[tuple[str, object]]:
    return [(kind, _engine(kind)[0]) for kind in (RPGM, RENPY)]


def active() -> tuple[str, str] | None:
    """The (kind, project_id) currently holding the GPU, if any."""
    if _task and not _task.done() and _active_id and _active_kind:
        return _active_kind, _active_id
    return None


def active_project_id() -> str | None:
    running = active()
    return running[1] if running else None


def is_running() -> bool:
    return active() is not None


async def _translate_one(
    source: str, target_lang: str, is_translatable: Callable[[str], bool]
) -> str:
    """Translate one unit.

    The result is used as-is. An earlier version compared the source's control
    codes against the translation's and held back any string where they
    differed, but Hy-MT2 preserves markup on its own, so that gate mostly
    withheld good translations. The only thing still refused is an empty
    response, which would blank a line in-game.
    """
    if not is_translatable(source):
        return source

    messages = build_messages(
        source,
        target_lang,
        None,
        config.DEFAULT_STYLE or None,
        glossary_store.merge_for(source, None),
        False,
        config.PROMPT_FORMAT,
        None,
    )
    translated = (await llama_client.chat_complete(messages)).strip()
    return translated or source


async def _run(kind: str, project_id: str, target_lang: str) -> None:
    store, is_translatable = _engine(kind)
    meta = store.load_meta(project_id)
    if meta is None:
        return

    units = store.load_units(project_id)
    translations = store.load_translations(project_id)

    pending = [u for u in units if u.source not in translations]
    meta["status"] = store.STATUS_TRANSLATING
    meta["target_lang"] = target_lang
    meta["translated_units"] = len(translations)
    store.save_meta(project_id, meta)

    # Recompute per-file done counts from what is already translated, so a
    # resumed job shows the right bars immediately instead of restarting at 0.
    done_slots = {name: 0 for name in meta["files"]}
    for unit in units:
        if unit.source in translations:
            for slot in unit.slots:
                if slot.file in done_slots:
                    done_slots[slot.file] += 1

    failed = int(meta.get("failed_units", 0))
    queue: asyncio.Queue = asyncio.Queue()
    for unit in pending:
        queue.put_nowait(unit)

    processed_since_flush = 0
    lock = asyncio.Lock()

    def flush() -> None:
        store.save_translations(project_id, translations)
        for name, count in done_slots.items():
            meta["files"][name]["done"] = count
        meta["translated_units"] = len(translations)
        meta["failed_units"] = failed
        store.save_meta(project_id, meta)

    async def worker() -> None:
        nonlocal processed_since_flush, failed
        while not _cancel:
            try:
                unit = queue.get_nowait()
            except asyncio.QueueEmpty:
                return
            try:
                text = await _translate_one(unit.source, target_lang, is_translatable)
            except Exception:  # noqa: BLE001 - one bad string must not kill the run
                # Backend error, not a bad translation: keep the source line so
                # the game still reads correctly, and count it so the total is
                # honest about what the model actually produced.
                text = unit.source
                async with lock:
                    failed += 1

            async with lock:
                translations[unit.source] = text
                for slot in unit.slots:
                    if slot.file in done_slots:
                        done_slots[slot.file] += 1
                processed_since_flush += 1
                if processed_since_flush >= _FLUSH_EVERY:
                    processed_since_flush = 0
                    flush()

    workers = [asyncio.create_task(worker()) for _ in range(config.PARALLEL_SLOTS)]
    try:
        await asyncio.gather(*workers)
    finally:
        flush()
        meta["status"] = (
            store.STATUS_CANCELLED
            if _cancel
            else store.STATUS_DONE
            if not queue.qsize()
            else store.STATUS_READY
        )
        meta["finished_at"] = time.time()
        store.save_meta(project_id, meta)


async def start(kind: str, project_id: str, target_lang: str) -> None:
    global _task, _cancel, _active_id, _active_kind
    if is_running():
        raise RuntimeError("A translation is already running")
    _cancel = False
    _active_id = project_id
    _active_kind = kind
    _task = asyncio.create_task(_run(kind, project_id, target_lang))


def cancel() -> bool:
    global _cancel
    if not is_running():
        return False
    _cancel = True
    return True


async def resume_pending() -> None:
    """Restart a run that a shutdown interrupted, whichever engine owned it."""
    if is_running():
        return
    for kind, store in stores():
        for meta in store.list_projects():
            if meta.get("status") == store.STATUS_TRANSLATING and meta.get("target_lang"):
                await start(kind, meta["id"], meta["target_lang"])
                return
