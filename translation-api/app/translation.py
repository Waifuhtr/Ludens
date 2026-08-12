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

# Opt-in only. Hy-MT2 already preserves placeholders and control codes
# (\V[1], %1, {var}, ...) on its own - verified against the 7B Q4_K_M model -
# so this clause is off by default: it costs prompt tokens without improving
# the result. Keep it to a single short sentence with no literal examples of
# the tokens themselves; a longer version listing sample placeholders gets
# treated as source text and translated instead of followed, which destroys
# short inputs ("Potion" came back as the translated instruction).
_PLACEHOLDER_CLAUSE = (
    ". You must keep every placeholder, variable and control code exactly as "
    "it appears, and must not translate, escape or reorder them"
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
    preserve_placeholders: bool = False,
) -> str:
    """Build a single-turn prompt in one of the instruction shapes documented on
    the Hy-MT2 model card. Everything the model is meant to *follow* has to stay
    inside the one instruction line - anything placed as its own paragraph ahead
    of the source text is read as more text to translate.
    """
    target_name = resolve_language(target_lang)

    if style:
        # "Style" template from the model card.
        instruction = (
            f"Please translate the following text into {target_name}. "
            f"Note that the translation style must strictly conform to [{style}]"
        )
    else:
        # "Default Translation" template from the model card.
        instruction = (
            f"Translate the following text into {target_name}. "
            "Note that you should only output the translated result "
            "without any additional explanation"
        )

    if source_lang:
        instruction += f". The source text is in {resolve_language(source_lang)}"

    if preserve_placeholders:
        instruction += _PLACEHOLDER_CLAUSE

    instruction += ":"

    if glossary:
        # "Terminology" template: reference pairs go *before* the task line.
        ref_lines = "\n".join(f"{k} translates to {v}" for k, v in glossary.items())
        instruction = (
            "Reference the following translations:\n" + ref_lines + "\n\n" + instruction
        )

    return f"{instruction}\n\n{text}"
