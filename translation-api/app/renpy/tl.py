"""Deliver translations for text that lives in compiled scripts.

A .rpyc cannot be edited: its syntax tree encodes the positions the engine
checks against, so text has to reach the player another way. Ren'Py provides
two, and a game that ships only .rpyc files needs both:

  config.say_menu_text_filter   every line of dialogue and every menu choice
                                passes through it before it is shown, keyed by
                                the untranslated text
  translate <lang> strings:     the interface strings the game marks with _()

Nothing here runs unless the upload actually contained a compiled script. A
project with its .rpy sources gets its text written straight into those files
and needs no runtime hook at all.

Two failure modes are designed out rather than tested for:

* Ren'Py 7.5 and later refuse to start if the same `old` string appears twice
  in a `translate strings:` block ("has been translated more than once"). The
  entries are keyed by source text and asserted unique before writing.
* A generated .rpy with a syntax error takes the whole game down on launch, so
  the Python half of the hook is compiled here before it is written.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..translation import LANGUAGES
from .text import escape

_JSON_NAME = "hymt_dialogue.json"
_HOOK_NAME = "hymt_translate.rpy"
_STRINGS_NAME = "hymt_strings.rpy"

# The Python that goes inside the hook's `init python:` block, kept here as
# plain source so it can be compiled before it is written into a .rpy.
_HOOK_BODY = '''\
import json
import os

def _hymt_load():
    path = os.path.join(config.gamedir, "tl", "__LANG__", "__JSON__")
    try:
        with open(path, "rb") as handle:
            return json.loads(handle.read().decode("utf-8"))
    except Exception:
        return {}

_hymt_map = _hymt_load()
_hymt_previous = getattr(config, "say_menu_text_filter", None)

def _hymt_filter(text):
    if _hymt_previous is not None:
        text = _hymt_previous(text)
    return _hymt_map.get(text, text)

config.say_menu_text_filter = _hymt_filter
'''


def language_name(target_lang: str) -> str:
    """Map a language code to the directory name Ren'Py uses.

    Ren'Py keys translations by an English language name in lower case
    ("turkish"), not by an ISO code, and the tl/ folder has to match.
    """
    code = (target_lang or "").strip().lower()
    name = LANGUAGES.get(code, code)
    return name.lower().replace(" ", "") or "translated"


def _render_hook(lang: str) -> str:
    body = _HOOK_BODY.replace("__LANG__", lang).replace("__JSON__", _JSON_NAME)
    # Fail here, in the generator, rather than in the player's game.
    compile(body, "<hymt hook>", "exec")

    indented = "\n".join(
        ("    " + line) if line.strip() else "" for line in body.splitlines()
    )
    return (
        "# Generated translation hook.\n"
        "#\n"
        "# The dialogue in this game is inside compiled .rpyc scripts, which\n"
        "# cannot be edited. This filter swaps each line for its translation\n"
        "# as the game displays it, and leaves anything untranslated alone.\n"
        "\n"
        "init python:\n" + indented + "\n"
    )


def _render_strings(lang: str, pairs: list[tuple[str, str]]) -> str:
    lines = [
        "# Generated interface translations.",
        "",
        f"translate {lang} strings:",
        "",
    ]
    for source, translated in pairs:
        lines.append(f'    old "{escape(source, chr(34))}"')
        lines.append(f'    new "{escape(translated, chr(34))}"')
        lines.append("")
    return "\n".join(lines)


def game_root(staging: Path, units: list) -> Path:
    """The directory the generated files belong in.

    Ren'Py resolves `config.gamedir` to the game's `game/` folder, and that is
    where tl/ has to live. Uploads arrive either as a game folder or as a bare
    pile of scripts, so the folder is found from where the scripts actually
    sit rather than assumed - putting the hook beside `game/` instead of
    inside it would leave the two halves of the output extracting to different
    places.
    """
    for unit in units:
        for slot in unit.slots:
            parts = Path(slot.file).parts
            if "game" in parts:
                return staging.joinpath(*parts[: parts.index("game") + 1])
    return staging


def write_runtime_translation(
    staging: Path,
    units: list,
    translations: dict[str, str],
    target_lang: str,
) -> list[Path]:
    """Write the hook, its data file and the strings block into `staging`.

    Returns the files created, which is empty when the project had no compiled
    scripts.
    """
    mapping: dict[str, str] = {}
    for unit in units:
        translated = translations.get(unit.source)
        if translated is None or translated == unit.source:
            continue
        if any(not slot.writable for slot in unit.slots):
            mapping[unit.source] = translated

    if not mapping:
        return []

    lang = language_name(target_lang)
    root = game_root(staging, units)
    tl_dir = root / "tl" / lang
    tl_dir.mkdir(parents=True, exist_ok=True)

    json_path = tl_dir / _JSON_NAME
    json_path.write_text(
        json.dumps(mapping, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    hook_path = root / _HOOK_NAME
    hook_path.write_text(_render_hook(lang), encoding="utf-8")

    # dict keys are unique by construction, so no `old` can repeat - the
    # condition Ren'Py refuses to start on.
    pairs = sorted(mapping.items())
    assert len({source for source, _ in pairs}) == len(pairs)
    strings_path = tl_dir / _STRINGS_NAME
    strings_path.write_text(_render_strings(lang, pairs), encoding="utf-8")

    return [json_path, hook_path, strings_path]
