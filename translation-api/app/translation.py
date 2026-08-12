"""Prompt construction for Hy-MT2, following the instruction formats documented
on https://huggingface.co/tencent/Hy-MT2-7B-GGUF ("Default Translation",
"Terminology", "Style" and "Structured Data" instruction variants).
"""

# The 33 languages Hy-MT2 is documented to support, code -> English name.
LANGUAGES = {
    "zh": "Chinese",
    "zh-hant": "Traditional Chinese",
    "yue": "Cantonese",
    "en": "English",
    "fr": "French",
    "pt": "Portuguese",
    "es": "Spanish",
    "ja": "Japanese",
    "tr": "Turkish",
    "ru": "Russian",
    "ar": "Arabic",
    "ko": "Korean",
    "th": "Thai",
    "it": "Italian",
    "de": "German",
    "vi": "Vietnamese",
    "ms": "Malay",
    "id": "Indonesian",
    "tl": "Filipino",
    "hi": "Hindi",
    "pl": "Polish",
    "cs": "Czech",
    "nl": "Dutch",
    "km": "Khmer",
    "my": "Burmese",
    "fa": "Persian",
    "gu": "Gujarati",
    "ur": "Urdu",
    "te": "Telugu",
    "mr": "Marathi",
    "he": "Hebrew",
    "bn": "Bengali",
    "ta": "Tamil",
    "uk": "Ukrainian",
    "bo": "Tibetan",
    "kk": "Kazakh",
    "mn": "Mongolian",
    "ug": "Uyghur",
}

# Placeholder styles commonly found in game strings (RPG Maker control codes,
# printf-style format specifiers, ICU/handlebars-style variables) that the
# model must copy through untouched rather than translate.
_PLACEHOLDER_HINT = (
    "You must NEVER translate or alter placeholders and control codes such as "
    r"\N[..], \V[..], \C[..], \I[..], {variable}, ${variable}, %s, %d, %1, {{var}} "
    "or similar tokens. Keep them exactly as they appear, in the same position."
)


def resolve_language(code_or_name: str) -> str:
    """Map an ISO-ish code to its English name; pass through unknown values
    (so callers can already supply a plain language name)."""
    return LANGUAGES.get(code_or_name.strip().lower(), code_or_name)


def build_prompt(
    text: str,
    target_lang: str,
    source_lang: str | None = None,
    style: str | None = None,
    glossary: dict[str, str] | None = None,
    preserve_placeholders: bool = True,
) -> str:
    target_name = resolve_language(target_lang)

    header = (
        f"Translate the following text into {target_name}. "
        "Note that you should only output the translated result "
        "without any additional explanation"
    )
    if source_lang:
        source_name = resolve_language(source_lang)
        header += f". The source text is in {source_name}"
    header += "."

    parts = [header]

    if style:
        parts.append(
            f"Note that the translation style must strictly conform to [{style}]."
        )

    if glossary:
        ref_lines = "\n".join(f"{k} translates to {v}" for k, v in glossary.items())
        parts.insert(
            0,
            "Reference the following translations:\n" + ref_lines,
        )

    if preserve_placeholders:
        parts.append(_PLACEHOLDER_HINT)

    instruction = "\n".join(parts)
    return f"{instruction}\n\n{text}"
