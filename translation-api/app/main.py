import asyncio
import time
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config, glossary as glossary_store, grouping, llama_client
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


@app.on_event("startup")
async def load_glossary():
    count = glossary_store.load(config.GLOSSARY_FILE)
    if config.GLOSSARY_FILE:
        print(f"[startup] glossary: {count} terms from {config.GLOSSARY_FILE}")


# Registered last so it can't shadow the API routes above: Starlette matches
# routes in registration order, and a "/" mount would otherwise catch
# everything not matched yet.
if _TEST_UI_DIR.is_dir():
    app.mount("/", StaticFiles(directory=_TEST_UI_DIR, html=True), name="test-ui")


@app.on_event("shutdown")
async def shutdown():
    await llama_client.aclose()
