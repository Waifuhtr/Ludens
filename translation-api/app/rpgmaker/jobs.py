"""The background translation run.

One job at a time, by design: there is a single GPU behind this, so a second
concurrent project would only make both finish later while doubling VRAM
pressure.

The run is restart-safe. Every completed string is written to
translations.json, and on startup a project still marked `translating` is
picked back up - it re-reads what is already done and only works through the
remainder, so a Space that sleeps mid-game resumes instead of starting over.
"""

from __future__ import annotations

import asyncio
import time

from .. import config, glossary as glossary_store, llama_client
from ..translation import build_messages, is_translatable
from . import store

# How often progress reaches disk. Small enough that a crash loses seconds of
# GPU time, large enough not to rewrite a growing JSON file per string.
_FLUSH_EVERY = 25

_task: asyncio.Task | None = None
_cancel = False
_active_id: str | None = None


def active_project_id() -> str | None:
    return _active_id if _task and not _task.done() else None


def is_running() -> bool:
    return active_project_id() is not None


async def _translate_one(source: str, target_lang: str) -> str:
    """Translate one unit.

    The result is used as-is. An earlier version compared the source's control
    codes against the translation's and held back any string where they
    differed, but Hy-MT2 preserves \\C[2], \\N[1] and friends on its own, so
    that gate mostly withheld good translations. The only thing still refused
    is an empty response, which would blank a line in-game.
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


async def _run(project_id: str, target_lang: str) -> None:
    global _cancel
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
                text = await _translate_one(unit.source, target_lang)
            except Exception:  # noqa: BLE001 - one bad string must not kill the run
                # Backend error, not a bad translation: keep the source line so
                # the game still reads correctly and count it so the total is
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


async def start(project_id: str, target_lang: str) -> None:
    global _task, _cancel, _active_id
    if is_running():
        raise RuntimeError("A translation is already running")
    _cancel = False
    _active_id = project_id
    _task = asyncio.create_task(_run(project_id, target_lang))


def cancel() -> bool:
    global _cancel
    if not is_running():
        return False
    _cancel = True
    return True


async def resume_pending() -> None:
    """Restart a run that a shutdown interrupted."""
    if is_running():
        return
    for meta in store.list_projects():
        if meta.get("status") == store.STATUS_TRANSLATING and meta.get("target_lang"):
            await start(meta["id"], meta["target_lang"])
            return
