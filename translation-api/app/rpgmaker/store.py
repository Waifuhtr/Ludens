"""On-disk state for uploaded projects.

Everything a running job needs lives in files, not memory, because the Space
sleeps and restarts: a job that has translated 40,000 strings must come back
after a restart with those 40,000 still done. Progress is flushed
periodically rather than per string, so a crash costs seconds of work, not
hours.
"""

from __future__ import annotations

import json
import shutil
import time
import uuid
import zipfile
from dataclasses import asdict
from pathlib import Path

from .. import config
from .extract import Slot, Unit, detect_data_root, extract

# Job lifecycle. `translating` is the only one a restart needs to resume.
STATUS_EXTRACTING = "extracting"
STATUS_READY = "ready"
STATUS_TRANSLATING = "translating"
STATUS_DONE = "done"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"


def root() -> Path:
    path = Path(config.PROJECT_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


def project_dir(project_id: str) -> Path:
    return root() / project_id


def _meta_path(project_id: str) -> Path:
    return project_dir(project_id) / "meta.json"


def load_meta(project_id: str) -> dict | None:
    try:
        return json.loads(_meta_path(project_id).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def save_meta(project_id: str, meta: dict) -> None:
    meta["updated_at"] = time.time()
    path = _meta_path(project_id)
    # Write-then-rename: a restart in the middle of a flush must not leave a
    # half-written meta.json that makes the project unreadable.
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    temp.replace(path)


def load_units(project_id: str) -> list[Unit]:
    raw = json.loads((project_dir(project_id) / "units.json").read_text(encoding="utf-8"))
    return [
        Unit(
            source=item["source"],
            slots=[Slot(file=s["file"], paths=s["paths"]) for s in item["slots"]],
        )
        for item in raw
    ]


def save_units(project_id: str, units: list[Unit]) -> None:
    (project_dir(project_id) / "units.json").write_text(
        json.dumps([asdict(u) for u in units], ensure_ascii=False), encoding="utf-8"
    )


def load_translations(project_id: str) -> dict[str, str]:
    path = project_dir(project_id) / "translations.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_translations(project_id: str, translations: dict[str, str]) -> None:
    path = project_dir(project_id) / "translations.json"
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(translations, ensure_ascii=False), encoding="utf-8")
    temp.replace(path)


def data_dir(project_id: str, meta: dict) -> Path:
    return project_dir(project_id) / "source" / meta["data_root"]


class UploadError(ValueError):
    """Raised for uploads that are not usable RPG Maker projects."""


def create(zip_bytes: bytes, name: str) -> dict:
    """Unpack an upload, find its data folder and index the dialogue."""
    if len(zip_bytes) > config.MAX_UPLOAD_MB * 1024 * 1024:
        raise UploadError(
            f"Upload is larger than {config.MAX_UPLOAD_MB} MB. Zip only the "
            "data folder (MZ) or www/data (MV), not the whole game."
        )

    project_id = uuid.uuid4().hex[:12]
    base = project_dir(project_id)
    source = base / "source"
    source.mkdir(parents=True, exist_ok=True)

    archive = base / "upload.zip"
    archive.write_bytes(zip_bytes)
    try:
        with zipfile.ZipFile(archive) as zf:
            for member in zf.infolist():
                # Reject absolute paths and ../ escapes rather than trusting
                # the archive to stay inside its own folder.
                target = (source / member.filename).resolve()
                if not str(target).startswith(str(source.resolve())):
                    raise UploadError(f"Unsafe path in zip: {member.filename}")
            zf.extractall(source)
    except zipfile.BadZipFile as exc:
        shutil.rmtree(base, ignore_errors=True)
        raise UploadError("Not a valid .zip file") from exc
    except UploadError:
        shutil.rmtree(base, ignore_errors=True)
        raise
    finally:
        archive.unlink(missing_ok=True)

    found = detect_data_root(source)
    if found is None:
        shutil.rmtree(base, ignore_errors=True)
        raise UploadError(
            "No RPG Maker data folder found in the zip. Expected a folder "
            "named 'data' (MZ) or 'www/data' (MV) containing System.json and "
            "Map*.json."
        )
    found_dir, engine = found

    units, broken = extract(found_dir)

    files: dict[str, dict] = {}
    for unit in units:
        for slot in unit.slots:
            entry = files.setdefault(slot.file, {"total": 0, "done": 0})
            entry["total"] += 1

    meta = {
        "id": project_id,
        "name": name,
        "engine": engine,
        "data_root": str(found_dir.relative_to(source)),
        "status": STATUS_READY,
        "created_at": time.time(),
        "updated_at": time.time(),
        "target_lang": None,
        "total_units": len(units),
        "total_slots": sum(f["total"] for f in files.values()),
        "translated_units": 0,
        "review_count": 0,
        "review_samples": [],
        "unreadable_files": broken,
        "files": files,
        "error": None,
    }
    save_units(project_id, units)
    save_translations(project_id, {})
    save_meta(project_id, meta)
    return meta


def list_projects() -> list[dict]:
    metas = []
    for child in root().iterdir():
        if child.is_dir():
            meta = load_meta(child.name)
            if meta:
                metas.append(meta)
    return sorted(metas, key=lambda m: m.get("created_at", 0), reverse=True)


def delete(project_id: str) -> bool:
    target = project_dir(project_id)
    if not target.is_dir():
        return False
    shutil.rmtree(target, ignore_errors=True)
    return True


def purge_expired() -> list[str]:
    """Delete projects untouched for longer than the retention window."""
    cutoff = time.time() - config.PROJECT_RETENTION_HOURS * 3600
    removed = []
    for meta in list_projects():
        if meta.get("updated_at", 0) < cutoff:
            if delete(meta["id"]):
                removed.append(meta["id"])
    return removed


def build_output(project_id: str, meta: dict) -> Path:
    """Produce the translated data folder as a downloadable zip.

    Rebuilt from the untouched source every time so a re-download after more
    strings finished reflects the newer state, and so a failed run never
    leaves a half-written tree behind.
    """
    from . import inject

    base = project_dir(project_id)
    staging = base / "build"
    shutil.rmtree(staging, ignore_errors=True)
    shutil.copytree(base / "source", staging)

    staged_data = staging / meta["data_root"]
    inject.apply(staged_data, load_units(project_id), load_translations(project_id))

    output = base / "translated.zip"
    output.unlink(missing_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(staging.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(staging))
    shutil.rmtree(staging, ignore_errors=True)
    return output
