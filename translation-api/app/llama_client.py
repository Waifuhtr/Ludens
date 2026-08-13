"""Thin async client for the internal llama-server instance.

llama-server is started with --parallel N --cont-batching (see entrypoint.sh),
which makes it batch multiple in-flight requests' forward passes together
instead of running them one at a time. This is where the actual CPU
efficiency gain for many short strings comes from: we just need to keep
enough requests in flight concurrently, and llama.cpp does the batching.
"""

import asyncio

import httpx

from . import config

_client: httpx.AsyncClient | None = None
# Bounds how many requests we hand to llama-server at once. Slightly above
# PARALLEL_SLOTS would over-queue on the server side instead of here; we
# keep it equal so backpressure is visible to callers via queueing time.
_semaphore = asyncio.Semaphore(config.PARALLEL_SLOTS)


def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            base_url=config.LLAMA_SERVER_URL,
            timeout=httpx.Timeout(config.REQUEST_TIMEOUT_SECONDS),
        )
    return _client


async def aclose() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


class LlamaServerError(RuntimeError):
    pass


async def chat_complete(
    messages: list[dict[str, str]], max_tokens: int | None = None
) -> str:
    client = get_client()
    payload = {
        "messages": messages,
        "temperature": config.TEMPERATURE,
        "top_p": config.TOP_P,
        "top_k": config.TOP_K,
        "repeat_penalty": config.REPEAT_PENALTY,
        "max_tokens": max_tokens or config.MAX_TOKENS,
        "stream": False,
    }
    async with _semaphore:
        try:
            resp = await client.post("/v1/chat/completions", json=payload)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise LlamaServerError(str(exc)) from exc

    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError) as exc:
        raise LlamaServerError(f"Unexpected llama-server response: {data}") from exc


async def health() -> bool:
    client = get_client()
    try:
        resp = await client.get("/health", timeout=5.0)
        return resp.status_code == 200
    except httpx.HTTPError:
        return False
