"""
make_icon.py
------------
Gera o ícone do aplicativo "GNSS Test" — um satélite estilizado — em alta
resolução e salva como .ico (multi-resolução) e .png.

Uso:
    python scripts/make_icon.py

Saída:
    src/lc76g_gnss/assets/gnss_test.ico
    src/lc76g_gnss/assets/gnss_test.png
"""

import math
import os

from PIL import Image, ImageDraw

S = 1024  # canvas de desenho em alta resolução
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "src", "lc76g_gnss", "assets")


def _lerp(c1, c2, t):
    return tuple(int(round(a + (b - a) * t)) for a, b in zip(c1, c2))


def _rounded_mask(size, radius):
    m = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return m


def _background():
    """Fundo quadrado arredondado com gradiente azul (céu/espaço)."""
    top, bottom = (10, 36, 99), (21, 101, 192)  # #0A2463 -> #1565C0
    img = Image.new("RGB", (S, S), top)
    d = ImageDraw.Draw(img)
    for y in range(S):
        d.line([(0, y), (S, y)], fill=_lerp(top, bottom, y / (S - 1)))
    img = img.convert("RGBA")
    img.putalpha(_rounded_mask(S, int(S * 0.22)))
    # leve brilho em estrelas
    stars = [(150, 200, 6), (820, 160, 7), (700, 300, 4), (240, 720, 5),
             (880, 720, 6), (130, 480, 4), (900, 430, 4)]
    sd = ImageDraw.Draw(img)
    for x, y, r in stars:
        sd.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, 210))
    return img


def _satellite_layer():
    """Desenha o satélite (corpo + painéis + antena) numa camada transparente."""
    lay = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    cx, cy = S // 2, S // 2

    navy, cyan = (11, 44, 94), (79, 195, 247)
    strut = (176, 190, 197)

    # Struts (hastes) ligando corpo aos painéis
    d.rectangle([cx - 330, cy - 14, cx + 330, cy + 14], fill=strut)

    # Painéis solares (dois), com grade de células
    pw, ph = 270, 150
    for sign in (-1, 1):
        x0 = cx + sign * 330 - (pw if sign > 0 else 0)
        if sign < 0:
            x0 = cx - 330 - pw
        x1, y0, y1 = x0 + pw, cy - ph // 2, cy + ph // 2
        d.rounded_rectangle([x0, y0, x1, y1], radius=14, fill=navy,
                            outline=cyan, width=6)
        for i in range(1, 4):  # 3 divisões verticais
            xx = x0 + pw * i // 4
            d.line([(xx, y0), (xx, y1)], fill=cyan, width=5)
        d.line([(x0, cy), (x1, cy)], fill=cyan, width=5)  # divisão horizontal

    # Corpo central (dourado)
    bw, bh = 190, 240
    bx0, by0, bx1, by1 = cx - bw // 2, cy - bh // 2, cx + bw // 2, cy + bh // 2
    d.rounded_rectangle([bx0, by0, bx1, by1], radius=26, fill=(255, 193, 7),
                        outline=(93, 64, 55), width=8)
    d.rectangle([bx0, cy - 20, bx1, cy + 20], fill=(255, 214, 90))

    # Antena/mastro com prato no topo
    d.line([(cx, by0), (cx, by0 - 120)], fill=strut, width=12)
    d.ellipse([cx - 95, by0 - 230, cx + 95, by0 - 90], fill=(236, 239, 241),
              outline=(120, 144, 156), width=8)
    d.ellipse([cx - 18, by0 - 175, cx + 18, by0 - 139], fill=(120, 144, 156))

    return lay


def _signal_waves(img):
    """Ondas de transmissão no canto superior direito."""
    d = ImageDraw.Draw(img)
    ox, oy = 760, 250  # origem das ondas
    d.ellipse([ox - 14, oy - 14, ox + 14, oy + 14], fill=(255, 255, 255, 255))
    for i, r in enumerate((70, 120, 170)):
        bbox = [ox - r, oy - r, ox + r, oy + r]
        d.arc(bbox, start=-70, end=20, fill=(255, 255, 255,
              230 - i * 40), width=16)
    return img


def build():
    os.makedirs(OUT_DIR, exist_ok=True)
    img = _background()
    sat = _satellite_layer().rotate(22, resample=Image.BICUBIC, center=(S // 2, S // 2))
    img.alpha_composite(sat)
    img = _signal_waves(img)

    png_path = os.path.join(OUT_DIR, "gnss_test.png")
    ico_path = os.path.join(OUT_DIR, "gnss_test.ico")
    img.resize((256, 256), Image.LANCZOS).save(png_path)
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128),
             (256, 256)]
    img.save(ico_path, format="ICO", sizes=sizes)
    print("Gerado:", ico_path)
    print("Gerado:", png_path)


if __name__ == "__main__":
    build()
