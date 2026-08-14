"""fontTools tabanlı kompozisyon motoru.

Bu modül; bir fontu belleğe yükleme, Türkçe karakterler için varsayılan
taslakları (recipe) otomatik hesaplama, canlı önizleme için SVG path üretme
ve son olarak yeni glyph'leri gerçek TTF/OTF'ye gömüp dışa aktarma işlerini
yapar.

Tasarım kararı: tüm glyph anahat verileri, fontTools "segment pen" protokolü
ile temsil edilir: her kontur, ``(operator, args)`` tuple'larından oluşan bir
listedir (moveTo/lineTo/curveTo/qCurveTo/closePath). Bu temsil hem TrueType
(quadratic) hem CFF (cubic) kaynaklı anahatları kayıpsız taşıyabildiği için
tüm birleştirme/dönüştürme/dışa aktarma kodu format bağımsız kalır.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Any, Optional

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

from . import recipes as R
from .synthetic_accents import synthetic_accent_contours

ContourOps = list[tuple[str, tuple]]
Bounds = tuple[float, float, float, float]


# --------------------------------------------------------------------------
# Temel yardımcılar
# --------------------------------------------------------------------------

def load_font(data: bytes) -> TTFont:
    font = TTFont(io.BytesIO(data))
    # lazy=False: tabloları hemen belleğe çöz, sonraki mutasyonlar güvenli olsun
    font.lazy = False
    return font


def save_font(font: TTFont) -> bytes:
    buf = io.BytesIO()
    font.save(buf)
    return buf.getvalue()


def is_cff(font: TTFont) -> bool:
    return "CFF " in font


def glyph_order_set(font: TTFont) -> set[str]:
    return set(font.getGlyphOrder())


def best_cmap(font: TTFont) -> dict[int, str]:
    try:
        return font.getBestCmap() or {}
    except Exception:
        return {}


def units_per_em(font: TTFont) -> int:
    return int(font["head"].unitsPerEm)


def get_font_info(font: TTFont, filename: str) -> dict[str, Any]:
    try:
        name_table = font["name"]
        family = name_table.getDebugName(16) or name_table.getDebugName(1) or "Bilinmiyor"
        subfamily = name_table.getDebugName(17) or name_table.getDebugName(2) or ""
    except Exception:
        family, subfamily = "Bilinmiyor", ""
    upm = units_per_em(font)
    hhea = font.get("hhea")
    ascender = int(hhea.ascender) if hhea is not None else int(upm * 0.8)
    descender = int(hhea.descender) if hhea is not None else int(-upm * 0.2)
    return {
        "filename": filename,
        "family_name": family,
        "subfamily_name": subfamily,
        "units_per_em": upm,
        "num_glyphs": len(font.getGlyphOrder()),
        "format": "CFF (OpenType)" if is_cff(font) else "TrueType (glyf)",
        "ascender": ascender,
        "descender": descender,
    }


def x_height(font: TTFont) -> float:
    try:
        v = font["OS/2"].sxHeight
        if v:
            return float(v)
    except Exception:
        pass
    return units_per_em(font) * 0.5


def split_into_contours(pen_value: list[tuple[str, tuple]]) -> list[ContourOps]:
    contours: list[ContourOps] = []
    current: ContourOps = []
    for op, args in pen_value:
        if op == "moveTo":
            if current:
                contours.append(current)
            current = [(op, args)]
        elif op in ("closePath", "endPath"):
            current.append((op, args))
            contours.append(current)
            current = []
        else:
            current.append((op, args))
    if current:
        contours.append(current)
    return contours


def decompose_glyph(font: TTFont, glyph_name: str) -> list[ContourOps]:
    glyph_set = font.getGlyphSet()
    if glyph_name not in glyph_set:
        return []
    pen = DecomposingRecordingPen(glyph_set)
    glyph_set[glyph_name].draw(pen)
    return split_into_contours(pen.value)


def contours_bounds(contours: list[ContourOps]) -> Optional[Bounds]:
    pen = BoundsPen(glyphSet=None)
    for contour in contours:
        for op, args in contour:
            getattr(pen, op)(*args)
    return pen.bounds


def _map_point(pt, dx: float, dy: float, sx: float, sy: float):
    if pt is None:
        return None
    x, y = pt
    return (x * sx + dx, y * sy + dy)


def transform_contours(contours: list[ContourOps], dx: float, dy: float, sx: float, sy: float) -> list[ContourOps]:
    out: list[ContourOps] = []
    for contour in contours:
        new_contour = []
        for op, args in contour:
            new_args = tuple(_map_point(p, dx, dy, sx, sy) for p in args)
            new_contour.append((op, new_args))
        out.append(new_contour)
    return out


def draw_contours(contours: list[ContourOps], pen) -> None:
    for contour in contours:
        for op, args in contour:
            getattr(pen, op)(*args)


def contours_to_svg_path(contours: list[ContourOps]) -> str:
    pen = SVGPathPen(glyphSet=None)
    draw_contours(contours, pen)
    return pen.getCommands()


# --------------------------------------------------------------------------
# Aksan kaynağı bulma (standalone glyph / donor / synthetic)
# --------------------------------------------------------------------------

def _find_standalone_accent(font: TTFont, cmap: dict[int, str], accent: str) -> Optional[str]:
    for cp in R.ACCENT_UNICODE_CANDIDATES.get(accent, []):
        name = cmap.get(cp)
        if name and name != ".notdef":
            return name
    agl_name = R.ACCENT_AGL_NAME.get(accent)
    if agl_name and agl_name in glyph_order_set(font):
        return agl_name
    return None


def _extract_donor_accent(font: TTFont, cmap: dict[int, str], accent: str) -> Optional[tuple[str, list[ContourOps]]]:
    """Fontta zaten bulunan bir precomposed karakterden (örn. 'ç') aksan
    şeklini konturların Y konumuna bakarak ayıklamayı dener."""
    donors = R.ACCENT_DONOR_CHARS.get(accent, "")
    upm = units_per_em(font)
    xh = x_height(font)
    placement = "below" if accent == "cedilla" else "above"
    for donor_char in donors:
        name = cmap.get(ord(donor_char))
        if not name:
            continue
        contours = decompose_glyph(font, name)
        if len(contours) < 2:
            continue  # tek konturlu glyph'ten aksan ayıklanamaz
        picked = []
        for c in contours:
            b = contours_bounds([c])
            if not b:
                continue
            _, c_ymin, _, c_ymax = b
            if placement == "above" and c_ymin > xh * 0.72:
                picked.append(c)
            elif placement == "below" and c_ymax < upm * 0.08:
                picked.append(c)
        if picked:
            return donor_char, picked
    return None


def resolve_accent(font: TTFont, cmap: dict[int, str], accent: str, base_bounds: Optional[Bounds]) -> dict[str, Any]:
    """Bir aksan tipi için en iyi kaynağı bulur.

    Dönüş: {"kind": "glyph"|"donor"|"synthetic", "ref": str,
            "contours": [...], "bounds": (xmin,ymin,xmax,ymax) | None,
            "warning": str | None}
    """
    standalone = _find_standalone_accent(font, cmap, accent)
    if standalone:
        contours = decompose_glyph(font, standalone)
        return {
            "kind": "glyph", "ref": standalone, "contours": contours,
            "bounds": contours_bounds(contours), "warning": None,
        }

    donor_result = _extract_donor_accent(font, cmap, accent)
    if donor_result:
        donor_char, contours = donor_result
        return {
            "kind": "donor", "ref": donor_char, "contours": contours,
            "bounds": contours_bounds(contours),
            "warning": f"Standalone '{accent}' glyph'i bulunamadı; şekil '{donor_char}' karakterinden otomatik ayıklandı.",
        }

    base_width = (base_bounds[2] - base_bounds[0]) if base_bounds else units_per_em(font) * 0.5
    upm = units_per_em(font)
    raw_contours = synthetic_accent_contours(accent, base_width, upm)
    contours: list[ContourOps] = []
    for poly in raw_contours:
        ops: ContourOps = [("moveTo", (poly[0],))]
        for pt in poly[1:]:
            ops.append(("lineTo", (pt,)))
        ops.append(("closePath", ()))
        contours.append(ops)
    return {
        "kind": "synthetic", "ref": accent, "contours": contours,
        "bounds": contours_bounds(contours),
        "warning": f"Fontta '{accent}' için hiçbir bileşen bulunamadı; yerleşik basit bir vektör şekli kullanıldı. Görsel uyum için elle bir aksan glyph'i seçmeniz önerilir.",
    }


def resolve_accent_by_source(font: TTFont, cmap: dict[int, str], accent_source: str, accent_type: str, base_bounds: Optional[Bounds]) -> dict[str, Any]:
    """Kullanıcının elle seçtiği ya da otomatik hesaplanmış accent_source
    değerine göre kontur verisini üretir. accent_source ya gerçek bir glyph
    adı, ya '__donor__:<char>' ya da '__synthetic__' olabilir."""
    if accent_source.startswith(R.DONOR_PREFIX):
        donor_char = accent_source.split(":", 1)[1]
        name = cmap.get(ord(donor_char)) if donor_char else None
        if name:
            upm = units_per_em(font)
            xh = x_height(font)
            placement = "below" if accent_type == "cedilla" else "above"
            contours = decompose_glyph(font, name)
            picked = []
            for c in contours:
                b = contours_bounds([c])
                if not b:
                    continue
                _, c_ymin, _, c_ymax = b
                if placement == "above" and c_ymin > xh * 0.72:
                    picked.append(c)
                elif placement == "below" and c_ymax < upm * 0.08:
                    picked.append(c)
            if picked:
                return {"kind": "donor", "ref": donor_char, "contours": picked, "bounds": contours_bounds(picked), "warning": None}
        return resolve_accent(font, cmap, accent_type, base_bounds)
    if accent_source.startswith(R.SYNTHETIC_PREFIX):
        base_width = (base_bounds[2] - base_bounds[0]) if base_bounds else units_per_em(font) * 0.5
        upm = units_per_em(font)
        raw_contours = synthetic_accent_contours(accent_type, base_width, upm)
        contours = []
        for poly in raw_contours:
            ops: ContourOps = [("moveTo", (poly[0],))]
            for pt in poly[1:]:
                ops.append(("lineTo", (pt,)))
            ops.append(("closePath", ()))
            contours.append(ops)
        return {"kind": "synthetic", "ref": accent_type, "contours": contours, "bounds": contours_bounds(contours), "warning": None}
    # gerçek glyph adı
    if accent_source in glyph_order_set(font):
        contours = decompose_glyph(font, accent_source)
        return {"kind": "glyph", "ref": accent_source, "contours": contours, "bounds": contours_bounds(contours), "warning": None}
    return resolve_accent(font, cmap, accent_type, base_bounds)


# --------------------------------------------------------------------------
# Otomatik konumlama
# --------------------------------------------------------------------------

def auto_offset(base_bounds: Bounds, accent_bounds: Bounds, placement: str, upm: float) -> tuple[float, float]:
    bx0, by0, bx1, by1 = base_bounds
    ax0, ay0, ax1, ay1 = accent_bounds
    base_cx = (bx0 + bx1) / 2
    accent_cx = (ax0 + ax1) / 2
    dx = base_cx - accent_cx
    gap = upm * 0.03
    if placement == "above":
        target_ymin = by1 + gap
        dy = target_ymin - ay0
    else:  # below (cedilla)
        overlap = upm * 0.05
        target_ymax = by0 + overlap
        dy = target_ymax - ay1
    return dx, dy


# --------------------------------------------------------------------------
# Karakter analizi (upload sonrası varsayılan taslakları üretir)
# --------------------------------------------------------------------------

@dataclass
class CharAnalysis:
    char: str
    codepoint: int
    label: str
    status: str  # present | existing_unmapped | composable | composable_synthetic | needs_attention
    recipe: dict[str, Any]
    warnings: list[str] = field(default_factory=list)


def analyze_font(font: TTFont) -> list[CharAnalysis]:
    cmap = best_cmap(font)
    go = glyph_order_set(font)
    results: list[CharAnalysis] = []

    for cdef in R.TURKISH_CHAR_DEFS:
        warnings: list[str] = []
        if cdef.codepoint in cmap:
            results.append(CharAnalysis(
                char=cdef.char, codepoint=cdef.codepoint, label=cdef.label,
                status="present", recipe={"mode": "skip"},
            ))
            continue

        agl_name = R.AGL_PRECOMPOSED_NAME.get(cdef.char)
        if agl_name and agl_name in go:
            results.append(CharAnalysis(
                char=cdef.char, codepoint=cdef.codepoint, label=cdef.label,
                status="existing_unmapped",
                recipe={"mode": "existing", "source_glyph": agl_name},
            ))
            continue

        base_name = cmap.get(ord(cdef.base_char))
        if not base_name:
            results.append(CharAnalysis(
                char=cdef.char, codepoint=cdef.codepoint, label=cdef.label,
                status="needs_attention",
                recipe={"mode": "skip", "base_glyph": None},
                warnings=[f"Temel harf '{cdef.base_char}' fontta bulunamadı."],
            ))
            continue

        base_bounds = contours_bounds(decompose_glyph(font, base_name))

        if cdef.placement == "dotless":
            dotless_name = cmap.get(0x0131) or ("dotlessi" if "dotlessi" in go else None)
            if dotless_name:
                results.append(CharAnalysis(
                    char=cdef.char, codepoint=cdef.codepoint, label=cdef.label,
                    status="existing_unmapped",
                    recipe={"mode": "existing", "source_glyph": dotless_name},
                ))
                continue
            cutoff = _auto_dotless_cutoff(font, base_name, base_bounds)
            status = "composable" if cutoff is not None else "needs_attention"
            if cutoff is None:
                warnings.append("'i' harfinin noktası otomatik tespit edilemedi; kesme çizgisini (cutoff) elle ayarlayın.")
                cutoff = x_height(font)
            results.append(CharAnalysis(
                char=cdef.char, codepoint=cdef.codepoint, label=cdef.label,
                status=status,
                recipe={"mode": "dotless", "base_glyph": base_name, "cutoff_y": cutoff},
                warnings=warnings,
            ))
            continue

        accent_info = resolve_accent(font, cmap, cdef.accent, base_bounds)
        if accent_info["warning"]:
            warnings.append(accent_info["warning"])
        dx, dy = 0.0, 0.0
        if base_bounds and accent_info["bounds"]:
            dx, dy = auto_offset(base_bounds, accent_info["bounds"], cdef.placement, units_per_em(font))

        source = accent_info["ref"]
        if accent_info["kind"] == "donor":
            source = f"{R.DONOR_PREFIX}:{accent_info['ref']}"
        elif accent_info["kind"] == "synthetic":
            source = f"{R.SYNTHETIC_PREFIX}:{accent_info['ref']}"

        status = "composable_synthetic" if accent_info["kind"] == "synthetic" else "composable"
        results.append(CharAnalysis(
            char=cdef.char, codepoint=cdef.codepoint, label=cdef.label,
            status=status,
            recipe={
                "mode": "compose",
                "base_glyph": base_name,
                "accent_source": source,
                "accent_type": cdef.accent,
                "dx": round(dx, 1), "dy": round(dy, 1),
                "scale_x": 1.0, "scale_y": 1.0,
            },
            warnings=warnings,
        ))
    return results


def _auto_dotless_cutoff(font: TTFont, base_name: str, base_bounds: Optional[Bounds]) -> Optional[float]:
    contours = decompose_glyph(font, base_name)
    if len(contours) < 2:
        return None
    xh = x_height(font)
    dot_candidates = []
    for c in contours:
        b = contours_bounds([c])
        if b and b[1] > xh * 0.55:
            dot_candidates.append(b)
    if not dot_candidates:
        return None
    lowest_dot_ymin = min(b[1] for b in dot_candidates)
    return round(lowest_dot_ymin - (units_per_em(font) * 0.015), 1)


# --------------------------------------------------------------------------
# Önizleme / derleme
# --------------------------------------------------------------------------

def build_char_contours(font: TTFont, cmap: dict[int, str], char_def: R.CharDef, recipe: dict[str, Any]) -> tuple[list[ContourOps], list[str]]:
    """Bir karakter için nihai (birleştirilmiş) kontur listesini üretir."""
    warnings: list[str] = []
    mode = recipe.get("mode", "skip")

    if mode == "dotless":
        base_name = recipe.get("base_glyph")
        cutoff_y = recipe.get("cutoff_y")
        contours = decompose_glyph(font, base_name) if base_name else []
        if cutoff_y is None:
            return contours, warnings
        kept = []
        for c in contours:
            b = contours_bounds([c])
            if b and b[1] >= cutoff_y:
                continue  # noktayı at
            kept.append(c)
        if len(kept) == len(contours):
            warnings.append("Kesme çizgisi hiçbir konturu kaldırmadı; 'ı' hâlâ nokta içerebilir.")
        return kept, warnings

    if mode == "compose":
        base_name = recipe.get("base_glyph")
        base_contours = decompose_glyph(font, base_name) if base_name else []
        base_bounds = contours_bounds(base_contours)
        accent_source = recipe.get("accent_source", "")
        accent_type = recipe.get("accent_type", "")
        accent_info = resolve_accent_by_source(font, cmap, accent_source, accent_type, base_bounds)
        if accent_info.get("warning"):
            warnings.append(accent_info["warning"])
        dx = float(recipe.get("dx", 0.0))
        dy = float(recipe.get("dy", 0.0))
        sx = float(recipe.get("scale_x", 1.0))
        sy = float(recipe.get("scale_y", 1.0))
        accent_contours = transform_contours(accent_info["contours"], dx, dy, sx, sy)
        return base_contours + accent_contours, warnings

    return [], warnings


def preview_svg_path(font: TTFont, char_def: R.CharDef, recipe: dict[str, Any]) -> dict[str, Any]:
    cmap = best_cmap(font)
    mode = recipe.get("mode")

    if mode == "existing":
        name = recipe.get("source_glyph")
        contours = decompose_glyph(font, name) if name else []
        bounds = contours_bounds(contours)
        width = font["hmtx"][name][0] if name in font["hmtx"].metrics else units_per_em(font) * 0.5
        return {
            "path": contours_to_svg_path(contours), "bounds": bounds,
            "advance_width": width, "warnings": [],
        }

    contours, warnings = build_char_contours(font, cmap, char_def, recipe)
    bounds = contours_bounds(contours)
    base_name = recipe.get("base_glyph")
    if base_name and base_name in font["hmtx"].metrics:
        width = font["hmtx"][base_name][0]
    else:
        width = units_per_em(font) * 0.5
    return {
        "path": contours_to_svg_path(contours), "bounds": bounds,
        "advance_width": width, "warnings": warnings,
    }


def add_glyph_to_font(font: TTFont, glyph_name: str, codepoint: int, contours: list[ContourOps], width: float) -> None:
    glyph_order = font.getGlyphOrder()
    if glyph_name not in glyph_order:
        glyph_order.append(glyph_name)
        font.setGlyphOrder(glyph_order)

    bounds = contours_bounds(contours)
    lsb = int(round(bounds[0])) if bounds else 0

    if "glyf" in font:
        pen = TTGlyphPen(font.getGlyphSet())
        draw_contours(contours, pen)
        glyph = pen.glyph()
        font["glyf"][glyph_name] = glyph
        glyph.recalcBounds(font["glyf"])
        lsb = glyph.xMin if getattr(glyph, "numberOfContours", 0) else 0
    elif "CFF " in font:
        cff = font["CFF "].cff
        top_dict = cff.topDictIndex[0]
        char_strings = top_dict.CharStrings
        private = getattr(top_dict, "Private", None)
        pen = T2CharStringPen(width, font.getGlyphSet())
        draw_contours(contours, pen)
        charstring = pen.getCharString(private=private, globalSubrs=cff.GlobalSubrs)
        if char_strings.charStringsAreIndexed:
            # Bu CharStrings, binary bir OTF'den okunduğu için isim->indeks
            # eşlemesi tutuyor; yeni glyph'i indekse ekleyip haritayı güncelle.
            new_index = len(char_strings.charStringsIndex)
            char_strings.charStringsIndex.append(charstring)
            char_strings.charStrings[glyph_name] = new_index
        else:
            char_strings.charStrings[glyph_name] = charstring
        if glyph_name not in top_dict.charset:
            top_dict.charset = list(top_dict.charset) + [glyph_name]
    else:
        raise ValueError("Desteklenmeyen font formatı: ne 'glyf' ne 'CFF ' tablosu var.")

    font["hmtx"][glyph_name] = (int(round(width)), lsb)

    for table in font["cmap"].tables:
        if table.isUnicode():
            table.cmap[codepoint] = glyph_name

    if "maxp" in font:
        font["maxp"].numGlyphs = len(font.getGlyphOrder())


def search_glyphs(font: TTFont, query: str, limit: int = 50) -> list[str]:
    names = font.getGlyphOrder()
    q = query.strip().lower()
    if not q:
        return names[:limit]
    starts = [n for n in names if n.lower().startswith(q)]
    contains = [n for n in names if q in n.lower() and n not in starts]
    return (starts + contains)[:limit]


def analysis_to_dict(a: CharAnalysis) -> dict[str, Any]:
    return {
        "char": a.char, "codepoint": a.codepoint, "label": a.label,
        "status": a.status, "recipe": a.recipe, "warnings": a.warnings,
    }


def build_font(original_bytes: bytes, char_recipes: dict[str, dict[str, Any]]) -> tuple[bytes, dict[str, list[str]]]:
    """Her karakter için recipe uygular ve nihai font bytes'ını döner.
    report: {char: [warnings/errors]}"""
    font = load_font(original_bytes)
    cmap = best_cmap(font)
    report: dict[str, list[str]] = {}
    char_defs = {c.char: c for c in R.TURKISH_CHAR_DEFS}

    for char, recipe in char_recipes.items():
        cdef = char_defs.get(char)
        if not cdef:
            continue
        mode = recipe.get("mode", "skip")
        msgs: list[str] = []
        try:
            if mode == "skip":
                continue
            elif mode == "existing":
                source = recipe.get("source_glyph")
                if not source or source not in glyph_order_set(font):
                    msgs.append(f"'{source}' glyph'i fontta bulunamadı, atlandı.")
                    report[char] = msgs
                    continue
                for table in font["cmap"].tables:
                    if table.isUnicode():
                        table.cmap[cdef.codepoint] = source
                msgs.append(f"Mevcut '{source}' glyph'i {char} için eşlendi.")
            else:
                contours, warnings = build_char_contours(font, cmap, cdef, recipe)
                msgs.extend(warnings)
                if not contours:
                    msgs.append("Üretilecek anahat bulunamadı, atlandı.")
                    report[char] = msgs
                    continue
                base_name = recipe.get("base_glyph")
                width = font["hmtx"][base_name][0] if base_name in font["hmtx"].metrics else units_per_em(font) // 2
                new_name = f"{cdef.char}.tr" if cdef.char.isalpha() else f"uni{cdef.codepoint:04X}"
                new_name = f"uni{cdef.codepoint:04X}.tr"
                add_glyph_to_font(font, new_name, cdef.codepoint, contours, width)
                msgs.append(f"'{new_name}' glyph'i oluşturuldu ve U+{cdef.codepoint:04X} olarak eşlendi.")
        except Exception as exc:  # noqa: BLE001
            msgs.append(f"Hata: {exc}")
        report[char] = msgs

    out_bytes = save_font(font)
    return out_bytes, report
