"""Fontta hiçbir gerçek aksan bileşeni bulunamadığında kullanılan, son çare
vektör aksan üreticileri. Sadece düz çizgi (lineTo) segmentleri kullanılır ki
hem TrueType (glyf/quadratic) hem CFF (cubic) hedef pen'lerine sorunsuz
aktarılabilsin.

Üretilen şekiller, verilen taban harfin (base) genişlik/yükseklik bilgisine
göre ölçeklenir; böylece farklı fontlarda makul bir varsayılan boyutla
başlarlar. Kullanıcı yine de X/Y ve ölçek alanlarından ince ayar yapabilir.
"""
from __future__ import annotations

import math

Point = tuple[float, float]
Contour = list[Point]


def _circle(cx: float, cy: float, rx: float, ry: float, n: int = 16) -> Contour:
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        pts.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
    return pts


def _cedilla_hook(width: float, height: float) -> Contour:
    # Basit bir virgül/kanca şekli; sol üstten başlar sağa iner, sola kıvrılır.
    steps = 14
    pts: list[Point] = []
    # gövde (kalın kısım) - küçük bir dörtgen üstte
    stem_w = width * 0.55
    pts += [(0, height * 0.55), (stem_w, height * 0.55), (stem_w, height * 0.85), (0, height * 0.85)]
    # kanca kuyruğu - üst sağdan aşağı sola bir yay
    cx, cy = width * 0.15, height * 0.15
    r = width * 0.42
    for i in range(steps + 1):
        a = math.radians(10 + i * (230 / steps))
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a) * 0.7 - height * 0.1))
    return pts


def _breve_arc(width: float, height: float) -> Contour:
    # Kalın kenarlı bir "u" (ters gülümseme) şekli - iki içiçe yay.
    steps = 20
    outer: list[Point] = []
    inner: list[Point] = []
    cx = width / 2
    r_out = width / 2
    r_in = r_out - height * 0.35
    for i in range(steps + 1):
        a = math.pi + math.pi * i / steps  # 180 -> 360 derece (alt yarım daire)
        outer.append((cx + r_out * math.cos(a), height * 0.9 + r_out * math.sin(a) * (height * 0.9 / r_out)))
    for i in range(steps + 1):
        a = math.pi + math.pi * (steps - i) / steps
        y = height * 0.9 + r_in * math.sin(a) * (height * 0.55 / max(r_in, 1))
        inner.append((cx + r_in * math.cos(a), max(y, height * 0.15)))
    return outer + inner


def _dot(width: float, height: float) -> Contour:
    r = min(width, height) / 2
    return _circle(width / 2, height / 2, r, r, n=14)


def synthetic_accent_contours(accent: str, base_width: float, upm: float) -> list[Contour]:
    """Verilen aksan tipi için taban harf genişliğine göre ölçeklenmiş,
    (0,0) yakınında konumlanmış kontur listesi döndürür."""
    w = max(base_width * 0.42, upm * 0.12)
    if accent == "dieresis":
        h = upm * 0.09
        dot_w = w * 0.32
        gap = w * 0.28
        left = _dot(dot_w, h)
        right = [(x + dot_w + gap, y) for x, y in left]
        return [left, right]
    if accent == "dotaccent":
        h = upm * 0.11
        return [_dot(w * 0.34, h)]
    if accent == "breve":
        h = upm * 0.14
        return [_breve_arc(w, h)]
    if accent == "cedilla":
        h = upm * 0.22
        return [_cedilla_hook(w * 0.6, h)]
    return []
