"""On-disk state for uploaded Ren'Py projects.

Kept apart from the RPG Maker projects in its own folder so neither engine can
ever read the other's metadata, and so listing one never has to filter out the
other.

Only scripts are ever unpacked. People upload whole `game/` folders that are
mostly art and audio, and none of it is read, so writing gigabytes to disk to
translate a few megabytes of text would be pure cost.
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
from .extract import SCRIPT_SUFFIXES, Slot, Unit, extract, has_scripts, is_skipped

STATUS_READY = "ready"
STATUS_TRANSLATING = "translating"
STATUS_DONE = "done"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"

KIND = "renpy"


def root() -> Path:
    path = Path(config.PROJECT_DIR) / "renpy"
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
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    temp.replace(path)


def load_units(project_id: str) -> list[Unit]:
    raw = json.loads((project_dir(project_id) / "units.json").read_text(encoding="utf-8"))
    return [
        Unit(
            source=item["source"],
            slots=[Slot(**slot) for slot in item["slots"]],
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


def source_dir(project_id: str) -> Path:
    return project_dir(project_id) / "source"


class UploadError(ValueError):
    """Raised for uploads that hold no usable Ren'Py script."""


def _unpack_scripts(archive: Path, target: Path) -> int:
    """Extract only the scripts from `archive`. Returns how many were written."""
    written = 0
    with zipfile.ZipFile(archive) as zf:
        for member in zf.infolist():
            if member.is_dir():
                continue
            name = Path(member.filename)
            if name.suffix.lower() not in SCRIPT_SUFFIXES:
                continue
            if is_skipped(name):
                continue

            destination = (target / member.filename).resolve()
            # Reject absolute paths and ../ escapes rather than trusting the
            # archive to stay inside its own folder.
            if not str(destination).startswith(str(target.resolve())):
                raise UploadError(f"Unsafe path in zip: {member.filename}")

            destination.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as incoming, open(destination, "wb") as outgoing:
                shutil.copyfileobj(incoming, outgoing)
            written += 1
    return written


def create(archive: Path, name: str) -> dict:
    """Unpack an upload's scripts and index the text in them."""
    project_id = uuid.uuid4().hex[:12]
    base = project_dir(project_id)
    source = source_dir(project_id)
    source.mkdir(parents=True, exist_ok=True)

    try:
        count = _unpack_scripts(archive, source)
    except zipfile.BadZipFile as exc:
        shutil.rmtree(base, ignore_errors=True)
        raise UploadError("Not a valid .zip file") from exc
    except UploadError:
        shutil.rmtree(base, ignore_errors=True)
        raise

    if not count or not has_scripts(source):
        shutil.rmtree(base, ignore_errors=True)
        raise UploadError(
            "No Ren'Py scripts found in the zip. Expected .rpy or .rpyc files - "
            "either on their own or inside a game folder."
        )

    units, broken = extract(source)

    files: dict[str, dict] = {}
    compiled = 0
    for unit in units:
        for slot in unit.slots:
            entry = files.setdefault(slot.file, {"total": 0, "done": 0})
            entry["total"] += 1
            if not slot.writable:
                compiled += 1

    meta = {
        "id": project_id,
        "kind": KIND,
        "name": name,
        "engine": "renpy",
        "status": STATUS_READY,
        "created_at": time.time(),
        "updated_at": time.time(),
        "target_lang": None,
        "total_units": len(units),
        "total_slots": sum(f["total"] for f in files.values()),
        "translated_units": 0,
        "failed_units": 0,
        "script_files": count,
        # Strings that came out of compiled scripts. They cannot be written
        # back into the .rpyc, so they travel in a generated translation file.
        "compiled_slots": compiled,
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
    cutoff = time.time() - config.PROJECT_RETENTION_HOURS * 3600
    removed = []
    for meta in list_projects():
        if meta.get("updated_at", 0) < cutoff:
            if delete(meta["id"]):
                removed.append(meta["id"])
    return removed


def build_output(project_id: str, meta: dict) -> Path:
    """Package the translated scripts.

    Only files that actually changed go in the zip. A Ren'Py game folder is
    mostly art and audio, and shipping it back unchanged would turn a few
    hundred kilobytes of script into a download the size of the game.
    """
    from . import inject, tl

    base = project_dir(project_id)
    staging = base / "build"
    shutil.rmtree(staging, ignore_errors=True)
    shutil.copytree(source_dir(project_id), staging)

    units = load_units(project_id)
    translations = load_translations(project_id)
    lang = meta.get("target_lang") or "translated"

    inject.apply(staging, units, translations)

    # Files that received at least one translation - the only ones worth
    # sending back.
    changed = {
        slot.file
        for unit in units
        if unit.source in translations
        for slot in unit.slots
        if slot.writable
    }

    generated = tl.write_runtime_translation(staging, units, translations, lang)

    output = base / "translated.zip"
    output.unlink(missing_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in sorted(changed):
            path = staging / name
            if path.is_file():
                zf.write(path, name)
        for path in generated:
            zf.write(path, path.relative_to(staging).as_posix())
    shutil.rmtree(staging, ignore_errors=True)
    return output
