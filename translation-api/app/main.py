import asyncio
import time

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import config, llama_client
from .translation import LANGUAGES, build_prompt

app = FastAPI(title="Hy-MT2 Translation API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    }


@app.get("/languages")
async def languages():
    return LANGUAGES


@app.post("/translate", response_model=TranslateResponse, dependencies=[Depends(verify_api_key)])
async def translate(req: TranslateRequest):
    prompt = build_prompt(
        req.text,
        req.target_lang,
        req.source_lang,
        req.style,
        req.glossary,
        req.preserve_placeholders,
    )
    start = time.perf_counter()
    try:
        translation = await llama_client.chat_complete(prompt)
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
        prompt = build_prompt(
            text,
            req.target_lang,
            req.source_lang,
            req.style,
            req.glossary,
            req.preserve_placeholders,
        )
        return await llama_client.chat_complete(prompt)

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


@app.on_event("shutdown")
async def shutdown():
    await llama_client.aclose()
