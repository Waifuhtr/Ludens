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


def _chaikin(points: list[Point], iterations: int = 3) -> list[Point]:
    """Köşeli bir çizgiyi (uç noktalar sabit kalacak şekilde) yumuşak bir
    eğriye yaklaştırır - basit ve kendi kendini kesme riski olmayan bir
    düzleştirme yöntemi."""
    pts = points
    for _ in range(iterations):
        smoothed = [pts[0]]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            smoothed.append((0.75 * x0 + 0.25 * x1, 0.75 * y0 + 0.25 * y1))
            smoothed.append((0.25 * x0 + 0.75 * x1, 0.25 * y0 + 0.75 * y1))
        smoothed.append(pts[-1])
        pts = smoothed
    return pts


def _stroke_polygon(centerline: list[Point], width_start: float, width_end: float) -> Contour:
    """Bir merkez çizgiyi, uca doğru inceltilmiş (tapered) tek bir kapalı
    poligona (dış kenar + ters yönde iç kenar) dönüştürür."""
    n = len(centerline)
    outer: list[Point] = []
    inner: list[Point] = []
    for i, (x, y) in enumerate(centerline):
        if i == 0:
            dx, dy = centerline[1][0] - x, centerline[1][1] - y
        elif i == n - 1:
            dx, dy = x - centerline[i - 1][0], y - centerline[i - 1][1]
        else:
            dx = centerline[i + 1][0] - centerline[i - 1][0]
            dy = centerline[i + 1][1] - centerline[i - 1][1]
        length = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / length, dx / length
        half = (width_start * (1 - i / (n - 1)) + width_end * (i / (n - 1))) / 2
        outer.append((x + nx * half, y + ny * half))
        inner.append((x - nx * half, y - ny * half))
    return outer + list(reversed(inner))


def _cedilla_hook(width: float, height: float) -> Contour:
    # Harfin altına tutunan, aşağı ve sola kıvrılan, ucu incelen tek parça bir kanca.
    key_points = [
        (width * 0.58, height * 1.00),  # üstte harfe tutunma noktası
        (width * 0.68, height * 0.70),  # sağa doğru omuz
        (width * 0.50, height * 0.38),  # merkeze doğru iniş
        (width * 0.24, height * 0.14),  # sola kıvrılma
        (width * 0.16, height * 0.00),  # incelen uç
    ]
    centerline = _chaikin(key_points, iterations=3)
    return _stroke_polygon(centerline, width_start=height * 0.30, width_end=height * 0.045)


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
