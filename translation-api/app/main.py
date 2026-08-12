import asyncio
import time
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config, llama_client
from .translation import LANGUAGES, build_messages

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


class BatchTranslateRequest(BaseModel):
    texts: list[str] = Field(..., min_length=1)
    target_lang: str
    source_lang: str | None = None
    style: str | None = None
    glossary: dict[str, str] | None = None
    preserve_placeholders: bool = False


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


@app.get("/health")
async def health_check():
    backend_ok = await llama_client.health()
    return {
        "status": "ok" if backend_ok else "starting",
        "llama_server": backend_ok,
        "parallel_slots": config.PARALLEL_SLOTS,
        "model_file": config.MODEL_FILE,
        "prompt_format": config.PROMPT_FORMAT,
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
        req.style,
        req.glossary,
        req.preserve_placeholders,
        config.PROMPT_FORMAT,
    )
    start = time.perf_counter()
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
        messages = build_messages(
            text,
            req.target_lang,
            req.source_lang,
            req.style,
            req.glossary,
            req.preserve_placeholders,
            config.PROMPT_FORMAT,
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


# Registered last so it can't shadow the API routes above: Starlette matches
# routes in registration order, and a "/" mount would otherwise catch
# everything not matched yet.
if _TEST_UI_DIR.is_dir():
    app.mount("/", StaticFiles(directory=_TEST_UI_DIR, html=True), name="test-ui")


@app.on_event("shutdown")
async def shutdown():
    await llama_client.aclose()
