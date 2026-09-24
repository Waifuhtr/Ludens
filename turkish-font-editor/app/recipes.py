"""Türkçe karakterler için varsayılan taslak (composition recipe) tanımları.

Her Türkçe karakter bir "temel harf" (base) ve bir "aksan" (accent) biriminin
birleşimi olarak tanımlanır. `placement` alanı aksanın harfe göre nereye
(üstüne / altına) yerleştirileceğini, otomatik konumlama mantığının hangi
kurala göre çalışacağını belirler.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CharDef:
    char: str
    codepoint: int
    base_char: str
    accent: Optional[str]  # None -> "dotless" modunda aksan kullanılmaz
    placement: str  # "above" | "below" | "dotless"
    label: str


TURKISH_CHAR_DEFS: list[CharDef] = [
    CharDef("Ç", 0x00C7, "C", "cedilla", "below", "C + Cedilla"),
    CharDef("ç", 0x00E7, "c", "cedilla", "below", "c + Cedilla"),
    CharDef("Ğ", 0x011E, "G", "breve", "above", "G + Breve"),
    CharDef("ğ", 0x011F, "g", "breve", "above", "g + Breve"),
    CharDef("İ", 0x0130, "I", "dotaccent", "above", "I + Dot"),
    CharDef("ı", 0x0131, "i", None, "dotless", "i'nin noktasız hali"),
    CharDef("Ö", 0x00D6, "O", "dieresis", "above", "O + Diaeresis"),
    CharDef("ö", 0x00F6, "o", "dieresis", "above", "o + Diaeresis"),
    CharDef("Ş", 0x015E, "S", "cedilla", "below", "S + Cedilla"),
    CharDef("ş", 0x015F, "s", "cedilla", "below", "s + Cedilla"),
    CharDef("Ü", 0x00DC, "U", "dieresis", "above", "U + Diaeresis"),
    CharDef("ü", 0x00FC, "u", "dieresis", "above", "u + Diaeresis"),
]

# Fontun kendi cmap'inde bu Unicode noktaları için standalone (tek başına)
# aksan glyph'i aranırken denenecek kod noktaları (spacing + combining).
ACCENT_UNICODE_CANDIDATES: dict[str, list[int]] = {
    "cedilla": [0x00B8, 0x0327],
    "breve": [0x02D8, 0x0306],
    "dieresis": [0x00A8, 0x0308],
    "dotaccent": [0x02D9, 0x0307],
}

# Adobe Glyph List standart isimleri - cmap'te olmasa bile glyph tablosunda
# bu isimle bir glyph varsa kullanılabilir.
ACCENT_AGL_NAME: dict[str, str] = {
    "cedilla": "cedilla",
    "breve": "breve",
    "dieresis": "dieresis",
    "dotaccent": "dotaccent",
}

# Standalone aksan glyph'i yoksa, bu karakterlerden (fontta zaten varsa)
# aksan şeklini "ödünç" almayı dene. Sırayla denenir.
ACCENT_DONOR_CHARS: dict[str, str] = {
    "cedilla": "çÇşŞģĢķĶļĻņŅŗŖţŢ",
    "breve": "ăĂĕĔğĞĭĬŏŎŭŬ",
    "dieresis": "äÄëËïÏöÖüÜÿŸ",
    "dotaccent": "żŻėĖ",
}

# Font zaten bu precomposed glyph'i standart isimle içeriyor olabilir
# (cmap'te eşlenmemiş olsa bile). Varsa çizim yapmaya gerek kalmaz,
# sadece cmap eşlemesi eklenir.
AGL_PRECOMPOSED_NAME: dict[str, str] = {
    "Ç": "Ccedilla", "ç": "ccedilla",
    "Ğ": "Gbreve", "ğ": "gbreve",
    "İ": "Idotaccent", "ı": "dotlessi",
    "Ö": "Odieresis", "ö": "odieresis",
    "Ş": "Scedilla", "ş": "scedilla",
    "Ü": "Udieresis", "ü": "udieresis",
}

DONOR_PREFIX = "__donor__"
SYNTHETIC_PREFIX = "__synthetic__"
