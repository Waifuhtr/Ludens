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


_STALE_NOTICE_NAME = "HYMT_DELETE_THESE_RPYC_FIRST.txt"

_STALE_NOTICE_HEADER = """\
Before copying the files from this zip into your game, delete these exact
files from your game folder (they will NOT be deleted by extracting this zip
- zip extraction only adds/overwrites files, it never removes anything):

"""

_STALE_NOTICE_FOOTER = """

Why: your project ships a precompiled .rpyc next to each .rpy. Ren'Py treats
the .rpy as the source of truth and the .rpyc as a disposable cache, but a
.rpyc left over from BEFORE translation no longer matches the .rpy you are
about to install - and Ren'Py running that stale compiled version against the
new source is what produces crashes like "must return a Text object" the
moment a translated line is reached. Deleting the .rpyc removes the mismatch:
Ren'Py recompiles a fresh one from the translated .rpy on next launch.
"""


_INSTALL_NOTICE_NAME = "HYMT_INSTALL.txt"

_INSTALL_ROOTED = """\
HOW TO INSTALL
==============

This zip mirrors your game's own folder layout, starting at the folder that
contains `game/`. Extract it over your game's root directory and answer
"replace" when asked - every file in here belongs exactly where it lands.
"""

_INSTALL_LOOSE = """\
HOW TO INSTALL
==============

You uploaded loose script files rather than a `game/` folder, so this zip has
no `game/` folder either. Everything in here belongs INSIDE your game's
`game/` folder:

  <YourGame>/game/hymt_translate.rpy
  <YourGame>/game/tl/<language>/...

Copy the contents of this zip into `<YourGame>/game/`, keeping the `tl/`
folder structure intact. Do not put them next to the .exe - Ren'Py only reads
scripts from inside `game/`.
"""

_INSTALL_FOOTER = """
Then start the game and choose the language, or set it in Preferences. Nothing
here overwrites your original scripts: the translations are additional files
that Ren'Py reads at runtime.
"""


def build_output(project_id: str, meta: dict) -> tuple[Path, list[str]]:
    """Package the translated scripts.

    Only files that actually changed go in the zip. A Ren'Py game folder is
    mostly art and audio, and shipping it back unchanged would turn a few
    hundred kilobytes of script into a download the size of the game.

    Returns the zip path and the list of stale sibling .rpyc files the caller
    still has on disk from before translation - see `_STALE_NOTICE_FOOTER`.
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

    # A .rpy we just edited may still have an untouched .rpyc sibling sitting
    # in the user's own game folder from before translation - never inside
    # this zip (extract() never reads it once a .rpy sibling exists), but
    # still on their disk, and now stale relative to the file we are about to
    # hand them.
    source = source_dir(project_id)
    stale_rpyc = sorted(
        name[:-4] + ".rpyc"
        for name in changed
        if name.endswith(".rpy") and (source / (name[:-4] + ".rpyc")).is_file()
    )

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
        if stale_rpyc:
            notice = _STALE_NOTICE_HEADER + "\n".join(stale_rpyc) + _STALE_NOTICE_FOOTER
            zf.writestr(_STALE_NOTICE_NAME, notice)
        # Where the files go depends on the shape of the upload, and getting it
        # wrong means the game simply ignores the translation with no error at
        # all - so it is spelled out rather than left to be inferred.
        rooted = tl.game_root(staging, units) != staging
        zf.writestr(
            _INSTALL_NOTICE_NAME,
            (_INSTALL_ROOTED if rooted else _INSTALL_LOOSE) + _INSTALL_FOOTER,
        )
    shutil.rmtree(staging, ignore_errors=True)
    return output, stale_rpyc
