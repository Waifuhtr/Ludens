from __future__ import annotations

import base64
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import font_engine as fe
from . import recipes as R

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR.parent / "static"

MAX_UPLOAD_BYTES = 30 * 1024 * 1024  # 30 MB
SESSION_TTL_SECONDS = 2 * 60 * 60  # 2 saat

app = FastAPI(title="Türkçe Font Tamamlayıcı")

_sessions: dict[str, dict[str, Any]] = {}
_sessions_lock = threading.Lock()


def _prune_sessions() -> None:
    now = time.time()
    expired = [sid for sid, s in _sessions.items() if now - s["created"] > SESSION_TTL_SECONDS]
    for sid in expired:
        _sessions.pop(sid, None)


def _get_session(session_id: str) -> dict[str, Any]:
    with _sessions_lock:
        _prune_sessions()
        session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Oturum bulunamadı ya da süresi doldu. Lütfen fontu yeniden yükleyin.")
    return session


CHAR_DEFS_BY_CHAR = {c.char: c for c in R.TURKISH_CHAR_DEFS}


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/upload")
async def upload_font(font: UploadFile = File(...)) -> dict[str, Any]:
    data = await font.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Dosya çok büyük (limit 30MB).")
    if not data:
        raise HTTPException(status_code=400, detail="Boş dosya.")

    try:
        parsed = fe.load_font(data)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Font okunamadı: {exc}") from exc

    if "glyf" not in parsed and "CFF " not in parsed:
        raise HTTPException(status_code=400, detail="Desteklenmeyen font formatı (ne TrueType ne CFF anahat verisi bulundu).")

    session_id = uuid.uuid4().hex
    filename = font.filename or "font"
    analysis = fe.analyze_font(parsed)

    with _sessions_lock:
        _prune_sessions()
        _sessions[session_id] = {
            "font": parsed,
            "original_bytes": data,
            "filename": filename,
            "created": time.time(),
        }

    return {
        "session_id": session_id,
        "font_info": fe.get_font_info(parsed, filename),
        "chars": [fe.analysis_to_dict(a) for a in analysis],
    }


@app.get("/api/glyphs")
def list_glyphs(session_id: str, q: str = "", limit: int = 50) -> dict[str, Any]:
    session = _get_session(session_id)
    limit = max(1, min(limit, 200))
    names = fe.search_glyphs(session["font"], q, limit)
    return {"glyphs": names}


class PreviewRequest(BaseModel):
    session_id: str
    char: str
    recipe: dict[str, Any]


@app.post("/api/preview")
def preview(req: PreviewRequest) -> dict[str, Any]:
    session = _get_session(req.session_id)
    cdef = CHAR_DEFS_BY_CHAR.get(req.char)
    if not cdef:
        raise HTTPException(status_code=400, detail="Bilinmeyen karakter.")
    font = session["font"]
    try:
        result = fe.preview_svg_path(font, cdef, req.recipe)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Önizleme oluşturulamadı: {exc}") from exc

    info = fe.get_font_info(font, session["filename"])
    return {
        "path": result["path"],
        "bounds": result["bounds"],
        "advance_width": result["advance_width"],
        "warnings": result["warnings"],
        "units_per_em": info["units_per_em"],
        "ascender": info["ascender"],
        "descender": info["descender"],
    }


class BuildRequest(BaseModel):
    session_id: str
    recipes: dict[str, dict[str, Any]]


def _output_filename(original: str, is_cff: bool) -> str:
    stem = Path(original).stem or "font"
    ext = ".otf" if is_cff else ".ttf"
    orig_ext = Path(original).suffix.lower()
    if orig_ext in (".ttf", ".otf"):
        ext = orig_ext
    return f"{stem}-TR{ext}"


@app.post("/api/build")
def build(req: BuildRequest) -> dict[str, Any]:
    session = _get_session(req.session_id)
    try:
        out_bytes, report = fe.build_font(session["original_bytes"], req.recipes)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Font oluşturulamadı: {exc}") from exc

    filename = _output_filename(session["filename"], fe.is_cff(session["font"]))
    return {
        "filename": filename,
        "font_base64": base64.b64encode(out_bytes).decode("ascii"),
        "report": report,
    }


@app.delete("/api/session/{session_id}")
def delete_session(session_id: str) -> dict[str, bool]:
    with _sessions_lock:
        _sessions.pop(session_id, None)
    return {"ok": True}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
