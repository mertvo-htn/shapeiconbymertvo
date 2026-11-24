"""Маски форм для иконок и применение формы к картинке (только Pillow, без Kivy)."""
import math
from functools import lru_cache

from PIL import Image, ImageChops, ImageDraw, ImageFilter

SS = 4  # суперсэмплинг для гладких краёв

# ключ -> название для интерфейса
SHAPES = {
    "circle": "Круг",
    "squircle": "Сквиркл",
    "rounded": "Скруглённый квадрат",
    "square": "Квадрат",
    "teardrop": "Капля",
    "hexagon": "Шестиугольник",
    "octagon": "Восьмиугольник",
    "diamond": "Ромб",
    "star": "Звезда",
    "flower": "Цветок",
    "heart": "Сердце",
}

BACKGROUNDS = {
    "transparent": "Прозрачный",
    "auto": "Авто (цвет иконки)",
    "white": "Белый",
    "dark": "Тёмный",
}


def _round_corners(mask, radius):
    """Скругляет острые углы многоугольника: размытие + порог."""
    mask = mask.filter(ImageFilter.GaussianBlur(radius))
    return mask.point(lambda v: 255 if v >= 128 else 0)


def _polygon(points, size, round_r):
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).polygon(points, fill=255)
    if round_r:
        mask = _round_corners(mask, round_r)
    return mask


def _regular(n, size, rot=-90, k=0.96):
    c, r = size / 2, size / 2 * k
    return [
        (c + r * math.cos(math.radians(rot + 360 * i / n)),
         c + r * math.sin(math.radians(rot + 360 * i / n)))
        for i in range(n)
    ]


def _build(shape, s):
    """Маска размера s×s (уже в увеличенном масштабе)."""
    if shape == "circle":
        m = Image.new("L", (s, s), 0)
        ImageDraw.Draw(m).ellipse((0, 0, s - 1, s - 1), fill=255)
        return m
    if shape == "square":
        return Image.new("L", (s, s), 255)
    if shape == "rounded":
        m = Image.new("L", (s, s), 0)
        ImageDraw.Draw(m).rounded_rectangle((0, 0, s - 1, s - 1), radius=int(s * 0.24), fill=255)
        return m
    if shape == "squircle":
        n, c, r = 5.0, s / 2, s / 2 - 1
        pts = []
        for i in range(720):
            t = 2 * math.pi * i / 720
            ct, st = math.cos(t), math.sin(t)
            x = math.copysign(abs(ct) ** (2 / n), ct)
            y = math.copysign(abs(st) ** (2 / n), st)
            pts.append((c + r * x, c + r * y))
        return _polygon(pts, s, 0)
    if shape == "teardrop":
        m = Image.new("L", (s, s), 0)
        d = ImageDraw.Draw(m)
        d.ellipse((0, 0, s - 1, s - 1), fill=255)
        d.rectangle((s // 2, 0, s - 1, s // 2), fill=255)  # острый угол сверху справа
        return m
    if shape == "hexagon":
        return _polygon(_regular(6, s, rot=-90, k=0.97), s, s * 0.03)
    if shape == "octagon":
        return _polygon(_regular(8, s, rot=-22.5, k=0.99), s, s * 0.02)
    if shape == "diamond":
        c = s / 2
        return _polygon([(c, 1), (s - 1, c), (c, s - 1), (1, c)], s, s * 0.04)
    if shape == "star":
        c, pts = s / 2, []
        for i in range(10):
            r = (c * 0.98) if i % 2 == 0 else (c * 0.5)
            a = math.radians(-90 + 36 * i)
            pts.append((c + r * math.cos(a), c + r * math.sin(a)))
        return _polygon(pts, s, s * 0.025)
    if shape == "flower":
        c, pts = s / 2, []
        for i in range(720):
            t = 2 * math.pi * i / 720
            r = c * (0.9 + 0.09 * math.cos(8 * t))
            pts.append((c + r * math.cos(t), c + r * math.sin(t)))
        return _polygon(pts, s, 0)
    if shape == "heart":
        raw = []
        for i in range(720):
            t = 2 * math.pi * i / 720
            x = 16 * math.sin(t) ** 3
            y = -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))
            raw.append((x, y))
        xs, ys = [p[0] for p in raw], [p[1] for p in raw]
        w, h = max(xs) - min(xs), max(ys) - min(ys)
        k = (s * 0.98) / max(w, h)
        ox = s / 2 - (max(xs) + min(xs)) / 2 * k
        oy = s / 2 - (max(ys) + min(ys)) / 2 * k
        return _polygon([(ox + x * k, oy + y * k) for x, y in raw], s, 0)
    raise ValueError(f"Неизвестная форма: {shape}")


@lru_cache(maxsize=64)
def get_mask(shape, size):
    """Маска формы размера size×size (режим L), кэшируется."""
    big = _build(shape, size * SS)
    return big.resize((size, size), Image.LANCZOS)


def _auto_color(img):
    """Средний цвет непрозрачных пикселей иконки."""
    small = img.resize((32, 32), Image.BILINEAR)
    r = g = b = n = 0
    for pr, pg, pb, pa in small.getdata():
        if pa > 200:
            r, g, b, n = r + pr, g + pg, b + pb, n + 1
    if not n:
        return (255, 255, 255, 255)
    return (r // n, g // n, b // n, 255)


def _bg_color(img, bg):
    if bg == "white":
        return (255, 255, 255, 255)
    if bg == "dark":
        return (32, 33, 36, 255)
    if bg == "auto":
        return _auto_color(img)
    return (0, 0, 0, 0)


def apply_shape(img, shape, size=192, scale=1.0, bg="transparent"):
    """Возвращает RGBA-иконку size×size, обрезанную по форме.

    scale — во сколько раз вписать исходную иконку (1.0 — по размеру холста,
    >1 — приблизить, <1 — уменьшить; свободное место заливается фоном).
    """
    img = img.convert("RGBA")
    canvas = Image.new("RGBA", (size, size), _bg_color(img, bg))

    w, h = img.size
    k = size * scale / max(w, h)
    nw, nh = max(1, round(w * k)), max(1, round(h * k))
    resized = img.resize((nw, nh), Image.LANCZOS)
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    layer.paste(resized, ((size - nw) // 2, (size - nh) // 2))
    canvas = Image.alpha_composite(canvas, layer)

    a = ImageChops.multiply(canvas.getchannel("A"), get_mask(shape, size))
    canvas.putalpha(a)
    return canvas
