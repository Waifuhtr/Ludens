import asyncio
import time
from pathlib import Path

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config, glossary as glossary_store, grouping, llama_client
from .rpgmaker import jobs as rpg_jobs, store as rpg_store
from .translation import LANGUAGES, build_messages, is_translatable

app = FastAPI(title="Translation API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serves test-ui/index.html at "/" so visiting the Space's URL shows the
# benchmark page instead of a bare 404 - the API routes below are registered
# first so this catch-all mount can't shadow them.
_TEST_UI_DIR = Path(__file__).resolve().parent.parent / "test-ui"


async def verify_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if config.API_KEY and x_api_key != config.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key header")


class TranslateRequest(BaseModel):
    text: str
    target_lang: str
    source_lang: str | None = None
    style: str | None = None
    glossary: dict[str, str] | None = None
    preserve_placeholders: bool = False
    context: str | None = None


class BatchTranslateRequest(BaseModel):
    texts: list[str] = Field(..., min_length=1)
    target_lang: str
    source_lang: str | None = None
    style: str | None = None
    glossary: dict[str, str] | None = None
    preserve_placeholders: bool = False
    context: str | None = None


class DocumentTranslateRequest(BaseModel):
    """Ordered lines of one scene/file, translated in groups so the model sees
    the surrounding dialogue instead of each line in isolation."""

    texts: list[str] = Field(..., min_length=1)
    target_lang: str
    source_lang: str | None = None
    style: str | None = None
    glossary: dict[str, str] | None = None
    preserve_placeholders: bool = False
    context: str | None = None
    group_size: int | None = None


class TranslateResponse(BaseModel):
    translation: str
    elapsed_seconds: float


class BatchItem(BaseModel):
    original: str
    translation: str | None
    error: str | None = None


class BatchTranslateResponse(BaseModel):
    translations: list[BatchItem]
    count: int
    elapsed_seconds: float
    items_per_second: float | None


class DocumentTranslateResponse(BatchTranslateResponse):
    groups: int
    group_size: int
    # Groups the model returned with the wrong markers, which were re-run one
    # string at a time. A number that keeps climbing means group_size is too
    # large for this model.
    regrouped_fallbacks: int


@app.get("/health")
async def health_check():
    backend_ok = await llama_client.health()
    return {
        "status": "ok" if backend_ok else "starting",
        "llama_server": backend_ok,
        "parallel_slots": config.PARALLEL_SLOTS,
        "model_file": config.MODEL_FILE,
        "prompt_format": config.PROMPT_FORMAT,
        "glossary_terms": glossary_store.size(),
        "group_size": config.GROUP_SIZE,
        "default_style": config.DEFAULT_STYLE or None,
    }


@app.get("/languages")
async def languages():
    return LANGUAGES


@app.post("/translate", response_model=TranslateResponse, dependencies=[Depends(verify_api_key)])
async def translate(req: TranslateRequest):
    messages = build_messages(
        req.text,
        req.target_lang,
        req.source_lang,
        req.style or config.DEFAULT_STYLE or None,
        glossary_store.merge_for(req.text, req.glossary),
        req.preserve_placeholders,
        config.PROMPT_FORMAT,
        req.context,
    )
    start = time.perf_counter()
    if not is_translatable(req.text):
        return TranslateResponse(translation=req.text, elapsed_seconds=0.0)
    try:
        translation = await llama_client.chat_complete(messages)
    except llama_client.LlamaServerError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    elapsed = time.perf_counter() - start
    return TranslateResponse(translation=translation, elapsed_seconds=round(elapsed, 4))


@app.post(
    "/translate/batch",
    response_model=BatchTranslateResponse,
    dependencies=[Depends(verify_api_key)],
)
async def translate_batch(req: BatchTranslateRequest):
    if len(req.texts) > config.MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Batch too large ({len(req.texts)} items). "
                f"Split into chunks of at most {config.MAX_BATCH_SIZE} "
                "(50-100 is a good size for many short strings)."
            ),
        )

    async def _translate_one(text: str):
        if not is_translatable(text):
            return text
        messages = build_messages(
            text,
            req.target_lang,
            req.source_lang,
            req.style or config.DEFAULT_STYLE or None,
            glossary_store.merge_for(text, req.glossary),
            req.preserve_placeholders,
            config.PROMPT_FORMAT,
            req.context,
        )
        return await llama_client.chat_complete(messages)

    start = time.perf_counter()
    results = await asyncio.gather(
        *(_translate_one(t) for t in req.texts), return_exceptions=True
    )
    elapsed = time.perf_counter() - start

    items: list[BatchItem] = []
    for original, result in zip(req.texts, results):
        if isinstance(result, Exception):
            items.append(BatchItem(original=original, translation=None, error=str(result)))
        else:
            items.append(BatchItem(original=original, translation=result))

    return BatchTranslateResponse(
        translations=items,
        count=len(req.texts),
        elapsed_seconds=round(elapsed, 4),
        items_per_second=round(len(req.texts) / elapsed, 2) if elapsed > 0 else None,
    )


@app.post(
    "/translate/document",
    response_model=DocumentTranslateResponse,
    dependencies=[Depends(verify_api_key)],
)
async def translate_document(req: DocumentTranslateRequest):
    if len(req.texts) > config.MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Document too long ({len(req.texts)} lines). "
                f"Split into chunks of at most {config.MAX_BATCH_SIZE} lines."
            ),
        )

    group_size = req.group_size or config.GROUP_SIZE
    if group_size < 1:
        raise HTTPException(status_code=400, detail="group_size must be >= 1")

    groups = grouping.chunk(req.texts, group_size)
    fallbacks = 0

    def _messages(text: str, glossary_source: str, numbered: bool):
        return build_messages(
            text,
            req.target_lang,
            req.source_lang,
            req.style or config.DEFAULT_STYLE or None,
            glossary_store.merge_for(glossary_source, req.glossary),
            req.preserve_placeholders,
            config.PROMPT_FORMAT,
            req.context,
            numbered,
        )

    async def _translate_single(text: str) -> str:
        if not is_translatable(text):
            return text
        return await llama_client.chat_complete(_messages(text, text, False))

    async def _translate_group(group: list[str]) -> list[str | Exception]:
        """One generation for the whole group; on any doubt about alignment,
        redo the group string by string so lines can never end up shifted."""
        nonlocal fallbacks

        # Control-code-only lines are copied through and kept out of the
        # numbered list entirely: they need no translation, and every segment
        # left in the group is one more chance for the model to miscount.
        results: list[str | Exception] = list(group)
        todo = [i for i, text in enumerate(group) if is_translatable(text)]
        if not todo:
            return results

        if len(todo) == 1:
            index = todo[0]
            try:
                results[index] = await _translate_single(group[index])
            except Exception as exc:  # noqa: BLE001 - surfaced per item below
                results[index] = exc
            return results

        payload = [group[i] for i in todo]
        try:
            # One generation now carries every segment, so the per-string
            # budget would truncate the tail and force a needless fallback.
            raw = await llama_client.chat_complete(
                _messages(grouping.encode(payload), "\n".join(payload), True),
                max_tokens=config.MAX_TOKENS * len(payload),
            )
            decoded = grouping.decode(raw, len(payload))
        except Exception:  # noqa: BLE001 - fall through to per-string retry
            decoded = None

        if decoded is None:
            fallbacks += 1
            decoded = await asyncio.gather(
                *(_translate_single(text) for text in payload), return_exceptions=True
            )

        for index, translated in zip(todo, decoded):
            results[index] = translated
        return results

    start = time.perf_counter()
    group_results = await asyncio.gather(*(_translate_group(g) for g in groups))
    elapsed = time.perf_counter() - start

    items: list[BatchItem] = []
    for group, results in zip(groups, group_results):
        for original, result in zip(group, results):
            if isinstance(result, Exception):
                items.append(
                    BatchItem(original=original, translation=None, error=str(result))
                )
            else:
                items.append(BatchItem(original=original, translation=result))

    return DocumentTranslateResponse(
        translations=items,
        count=len(req.texts),
        elapsed_seconds=round(elapsed, 4),
        items_per_second=round(len(req.texts) / elapsed, 2) if elapsed > 0 else None,
        groups=len(groups),
        group_size=group_size,
        regrouped_fallbacks=fallbacks,
    )


# ---------------------------------------------------------------------------
# RPG Maker MV/MZ projects
# ---------------------------------------------------------------------------


def _status_payload(meta: dict) -> dict:
    total = meta.get("total_units", 0) or 0
    done = meta.get("translated_units", 0) or 0
    files = [
        {
            "file": name,
            "total": stats["total"],
            "done": stats["done"],
            "percent": round(100 * stats["done"] / stats["total"], 1)
            if stats["total"]
            else 100.0,
        }
        for name, stats in sorted(meta.get("files", {}).items())
    ]
    return {
        "id": meta["id"],
        "name": meta.get("name"),
        "engine": meta.get("engine"),
        "status": meta.get("status"),
        "target_lang": meta.get("target_lang"),
        "total_units": total,
        "total_slots": meta.get("total_slots", 0),
        "translated_units": done,
        "percent": round(100 * done / total, 1) if total else 0.0,
        "failed_units": meta.get("failed_units", 0),
        "unreadable_files": meta.get("unreadable_files", []),
        "running": rpg_jobs.active_project_id() == meta["id"],
        "files": files,
        "error": meta.get("error"),
    }


def _require_project(project_id: str) -> dict:
    meta = rpg_store.load_meta(project_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Unknown project")
    return meta


@app.post("/project/upload", dependencies=[Depends(verify_api_key)])
async def upload_project(file: UploadFile = File(...)):
    """Accept a zipped RPG Maker data folder and index its dialogue."""
    rpg_store.purge_expired()
    payload = await file.read()
    try:
        meta = await asyncio.to_thread(
            rpg_store.create, payload, file.filename or "project.zip"
        )
    except rpg_store.UploadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _status_payload(meta)


@app.get("/project", dependencies=[Depends(verify_api_key)])
async def list_projects():
    return {
        "projects": [_status_payload(m) for m in rpg_store.list_projects()],
        "running": rpg_jobs.active_project_id(),
        "retention_hours": config.PROJECT_RETENTION_HOURS,
    }


@app.get("/project/{project_id}/status", dependencies=[Depends(verify_api_key)])
async def project_status(project_id: str):
    return _status_payload(_require_project(project_id))


class StartTranslationRequest(BaseModel):
    target_lang: str = "tr"


@app.post("/project/{project_id}/start", dependencies=[Depends(verify_api_key)])
async def start_project(project_id: str, req: StartTranslationRequest):
    meta = _require_project(project_id)
    if not await llama_client.health():
        raise HTTPException(
            status_code=503,
            detail="The model is still loading. Try again in a moment.",
        )
    try:
        await rpg_jobs.start(project_id, req.target_lang)
    except RuntimeError as exc:
        # One GPU, one job: say which project is holding it.
        raise HTTPException(
            status_code=409,
            detail=f"{exc} (project {rpg_jobs.active_project_id()})",
        ) from exc
    meta["status"] = rpg_store.STATUS_TRANSLATING
    meta["target_lang"] = req.target_lang
    return _status_payload(meta)


@app.post("/project/{project_id}/cancel", dependencies=[Depends(verify_api_key)])
async def cancel_project(project_id: str):
    _require_project(project_id)
    if rpg_jobs.active_project_id() != project_id:
        raise HTTPException(status_code=409, detail="That project is not running")
    rpg_jobs.cancel()
    return {"cancelling": True}


@app.get("/project/{project_id}/download", dependencies=[Depends(verify_api_key)])
async def download_project(project_id: str):
    """Rebuild the data folder with whatever is translated so far.

    Deliberately available before the run finishes: untranslated strings keep
    their source text, so a partial download is always a playable game rather
    than a broken one.
    """
    meta = _require_project(project_id)
    output = await asyncio.to_thread(rpg_store.build_output, project_id, meta)
    stem = Path(meta.get("name") or project_id).stem
    return FileResponse(
        output,
        media_type="application/zip",
        filename=f"{stem}-{meta.get('target_lang') or 'translated'}.zip",
    )


@app.delete("/project/{project_id}", dependencies=[Depends(verify_api_key)])
async def delete_project(project_id: str):
    if rpg_jobs.active_project_id() == project_id:
        rpg_jobs.cancel()
    if not rpg_store.delete(project_id):
        raise HTTPException(status_code=404, detail="Unknown project")
    return {"deleted": project_id}


@app.on_event("startup")
async def load_glossary():
    count = glossary_store.load(config.GLOSSARY_FILE)
    if config.GLOSSARY_FILE:
        print(f"[startup] glossary: {count} terms from {config.GLOSSARY_FILE}")


@app.on_event("startup")
async def resume_translation_jobs():
    """Pick up a run the last shutdown interrupted, and drop stale uploads.

    The Space sleeps; without this a project that was 90% translated would sit
    at 90% forever and have to be restarted by hand.
    """
    removed = rpg_store.purge_expired()
    if removed:
        print(f"[startup] purged {len(removed)} expired project(s)")
    await rpg_jobs.resume_pending()
    resumed = rpg_jobs.active_project_id()
    if resumed:
        print(f"[startup] resumed translation of project {resumed}")


# Registered last so it can't shadow the API routes above: Starlette matches
# routes in registration order, and a "/" mount would otherwise catch
# everything not matched yet.
if _TEST_UI_DIR.is_dir():
    app.mount("/", StaticFiles(directory=_TEST_UI_DIR, html=True), name="test-ui")


@app.on_event("shutdown")
async def shutdown():
    await llama_client.aclose()
