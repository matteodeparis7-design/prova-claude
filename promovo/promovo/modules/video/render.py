"""Agente "Montatore": video promozionali da qualsiasi volantino.

Formati: 16:9 (schermi in negozio), 9:16 (Reel, Storie, TikTok), 1:1 (post).
Scene: apertura con logo e periodo, una scena per offerta, chiusura con contatti e QR code.
Il disegno grafico (sfondi, cartellini, prodotti scontornati) è condiviso con le grafiche statiche.
I fotogrammi si disegnano con Pillow e si codificano in H.264 con ffmpeg; la musica è originale.
"""
from __future__ import annotations

import io
import math
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from ...money import price_parts

FONT_DIR = Path(__file__).resolve().parents[2] / "assets" / "fonts"

FORMATS = {
    "landscape": (1920, 1080),
    "portrait": (1080, 1920),
    "square": (1080, 1080),
}

INK = (20, 27, 45)
PAPER = (250, 247, 240)
WHITE = (255, 255, 255)


class RenderError(RuntimeError):
    pass


@dataclass
class VideoOffer:
    name: str
    description: str
    price_cents: int
    old_price_cents: int | None
    discount_percent: int | None
    conditions: str
    image_path: str | None
    brand: str = ""
    unit_price_text: str = ""


@dataclass
class VideoSpec:
    store_name: str
    headline: str                       # es. "Le offerte della settimana"
    validity: str                       # es. "dal 13 al 22 novembre"
    address: str
    offers: list[VideoOffer]
    brand_color: str = "#D7262E"
    accent_color: str = "#FFD23F"
    format: str = "landscape"
    fps: int = 25
    intro_seconds: float = 2.8
    offer_seconds: float = 3.4
    outro_seconds: float = 4.0
    scale: float = 1.0                  # <1 per anteprime veloci
    footer_note: str = "Offerte valide fino a esaurimento scorte. Le foto sono indicative."
    logo_path: str | None = None
    contact_lines: list[str] = field(default_factory=list)    # es. orari, WhatsApp
    qr_data: str = ""                    # link del QR code nella scena finale
    qr_label: str = ""
    music: bool = False
    warnings: list[str] = field(default_factory=list)
    idea_headline: bool = False         # il titolo è l'idea della settimana: protagonista dell'apertura


# ---------------------------------------------------------------- utilità grafiche

def hex_rgb(value: str) -> tuple[int, int, int]:
    v = value.lstrip("#")
    if len(v) != 6:
        raise ValueError(f"Colore non valido: {value}")
    return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def luminance(rgb: tuple[int, int, int]) -> float:
    def ch(c: int) -> float:
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def text_on(bg: tuple[int, int, int]) -> tuple[int, int, int]:
    """Testo chiaro o scuro, quello con più contrasto sullo sfondo."""
    return INK if luminance(bg) > 0.4 else WHITE


def mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))  # type: ignore[return-value]


def readable_on_paper(color: tuple[int, int, int]) -> tuple[int, int, int]:
    """Il colore del negozio, scurito se è troppo chiaro per essere letto su fondo chiaro."""
    c = color
    for _ in range(10):
        if luminance(c) < 0.35:
            return c
        c = mix(c, INK, 0.25)
    return c


@lru_cache(maxsize=96)
def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return ImageFont.truetype(str(FONT_DIR / name), max(8, int(size)))


def wrap(text: str, fnt: ImageFont.FreeTypeFont, max_width: int, max_lines: int) -> list[str]:
    # il simbolo dell'euro resta sempre attaccato al suo numero ("€ 8,26" non va mai a capo)
    text = re.sub(r"€ (?=\d)", "€\u00a0", " ".join(text.split()))
    words = [w for w in text.split(" ") if w]
    lines: list[str] = []
    cur = ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if fnt.getlength(trial) <= max_width:
            cur = trial
            continue
        if cur:
            lines.append(cur)
        cur = w
        if fnt.getlength(cur) > max_width:     # parola più larga della riga: si tronca
            while len(cur) > 1 and fnt.getlength(cur + "…") > max_width:
                cur = cur[:-1]
            cur += "…"
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while last and fnt.getlength(last + "…") > max_width:
            last = last[:-1]
        lines[-1] = last.rstrip() + "…"
    return lines


def fit_text(text: str, max_width: int, max_height: int, start: int, bold: bool, max_lines: int,
             min_size: int = 14) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    size = start
    while size >= min_size:
        f = font(size, bold)
        lines = wrap(text, f, max_width, max_lines)
        total = len(lines) * int(size * 1.16)
        if total <= max_height and not any(line.endswith("…") for line in lines[:-1]) and \
                all(f.getlength(line) <= max_width for line in lines) and \
                (len(lines) < max_lines or not lines[-1].endswith("…")):
            return f, lines
        size = int(size * 0.92)
    f = font(min_size, bold)
    return f, wrap(text, f, max_width, max_lines)


def text_layer(lines: list[str], fnt: ImageFont.FreeTypeFont, color: tuple[int, int, int],
               align: str = "left", line_gap: float = 1.16) -> Image.Image:
    lh = int(fnt.size * line_gap)
    width = max((int(math.ceil(fnt.getlength(line))) for line in lines), default=1) + 6
    height = max(lh * (len(lines) - 1) + int(fnt.size * 1.25), 1)
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        w = fnt.getlength(line)
        x = 0 if align == "left" else (width - w) / 2 if align == "center" else width - w
        d.text((x, i * lh), line, font=fnt, fill=color + (255,))
    return img


def ease_out(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def ease_in(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return x ** 3


def ease_back(x: float, s: float = 1.7) -> float:
    x = min(max(x, 0.0), 1.0) - 1
    return 1 + (s + 1) * x ** 3 + s * x ** 2


def with_alpha(img: Image.Image, alpha: float) -> Image.Image:
    if alpha >= 0.999:
        return img
    out = img.copy()
    out.putalpha(out.getchannel("A").point(lambda v: int(v * max(0.0, alpha))))
    return out


def paste(canvas: Image.Image, layer: Image.Image, x: float, y: float, alpha: float = 1.0) -> None:
    if alpha <= 0.002:
        return
    canvas.alpha_composite(with_alpha(layer, alpha), (int(round(x)), int(round(y))))


def scaled(img: Image.Image, s: float) -> Image.Image:
    if abs(s - 1) < 0.004:
        return img
    return img.resize((max(1, int(img.width * s)), max(1, int(img.height * s))), Image.BILINEAR)


def paste_center(canvas: Image.Image, layer: Image.Image, cx: float, cy: float, scale: float = 1.0,
                 alpha: float = 1.0) -> None:
    lay = scaled(layer, scale)
    paste(canvas, lay, cx - lay.width / 2, cy - lay.height / 2, alpha)


def shadow_of(img: Image.Image, blur: float, opacity: float) -> Image.Image:
    pad = int(blur * 3)
    a = img.getchannel("A").point(lambda v: int(v * opacity))
    sh = Image.new("RGBA", (img.width + 2 * pad, img.height + 2 * pad), (0, 0, 0, 0))
    black = Image.new("RGBA", img.size, INK + (255,))
    black.putalpha(a)
    sh.alpha_composite(black, (pad, pad))
    return sh.filter(ImageFilter.GaussianBlur(blur))


# ---------------------------------------------------------------- elementi grafici condivisi

def soft_background(w: int, h: int, brand: tuple[int, int, int], u: float) -> Image.Image:
    """Sfondo chiaro con sfumatura del colore del negozio e due grandi aloni morbidi."""
    top, bottom = mix(brand, WHITE, 0.91), PAPER
    grad = Image.linear_gradient("L").resize((w, h))
    bg = Image.composite(Image.new("RGB", (w, h), bottom), Image.new("RGB", (w, h), top), grad)
    # Gli aloni si disegnano in RGB e si sfocano insieme allo sfondo: nessun bordo grigio.
    deco = bg.copy()
    d = ImageDraw.Draw(deco)
    r1, r2 = 560 * u, 420 * u
    d.ellipse((w - r1 * 1.1, -r1 * 0.6, w + r1 * 0.9, r1 * 1.4), fill=mix(brand, WHITE, 0.82))
    d.ellipse((-r2 * 0.9, h - r2 * 1.1, r2 * 1.1, h + r2 * 0.9), fill=mix(brand, WHITE, 0.86))
    deco = deco.filter(ImageFilter.GaussianBlur(70 * u))
    return Image.blend(bg, deco, 0.85).convert("RGBA")


def brand_background(w: int, h: int, brand: tuple[int, int, int], accent: tuple[int, int, int],
                     u: float) -> Image.Image:
    """Sfondo pieno del colore del negozio, con un alone di luce e raggi leggeri."""
    dark = mix(brand, INK, 0.38)
    grad = Image.linear_gradient("L").resize((w, h))
    bg = Image.composite(Image.new("RGB", (w, h), dark), Image.new("RGB", (w, h), brand), grad)
    cx, cy = w * 0.5, h * 0.42
    light = bg.copy()
    d = ImageDraw.Draw(light)
    big = max(w, h) * 1.3
    ray = mix(brand, WHITE, 0.12)
    for i in range(12):
        a0 = i * 30
        pts = [(cx, cy)] + [(cx + big * math.cos(math.radians(a)), cy + big * math.sin(math.radians(a)))
                             for a in (a0, a0 + 12)]
        d.polygon(pts, fill=ray)
    light = light.filter(ImageFilter.GaussianBlur(4 * u))
    bg = Image.blend(bg, light, 0.55)
    glow = bg.copy()
    ImageDraw.Draw(glow).ellipse((cx - 460 * u, cy - 460 * u, cx + 460 * u, cy + 460 * u), fill=mix(brand, WHITE, 0.3))
    glow = glow.filter(ImageFilter.GaussianBlur(150 * u))
    return Image.blend(bg, glow, 0.6).convert("RGBA")


def price_block(cents: int, height: int, color: tuple[int, int, int]) -> Image.Image:
    """Cartellino del prezzo: euro grandi, centesimi in alto e simbolo € sotto i centesimi."""
    euros, dec = price_parts(cents)
    big = font(int(height * 0.62), True)
    small = font(int(height * 0.27), True)
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    eb = probe.textbbox((0, 0), euros, font=big, anchor="ls")
    db = probe.textbbox((0, 0), f",{dec}", font=small, anchor="lt")
    sb = probe.textbbox((0, 0), "€", font=small, anchor="ls")
    w_e, w_r = eb[2] - eb[0], max(db[2] - db[0], sb[2] - sb[0])
    gap = height * 0.04
    pad_x = height * 0.26
    width = int(w_e + gap + w_r + 2 * pad_x)
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, width - 1, height - 1), radius=int(height * 0.2), fill=color + (255,))
    fg = text_on(color)
    cap = -eb[1]
    base = (height + cap) / 2
    x = pad_x - eb[0]
    d.text((x, base), euros, font=big, fill=fg, anchor="ls")
    x2 = x + eb[2] + gap
    d.text((x2, base - cap), f",{dec}", font=small, fill=fg, anchor="lt")
    d.text((x2, base), "€", font=small, fill=fg, anchor="ls")
    return img


def discount_burst(pct: int, size: int, color: tuple[int, int, int]) -> Image.Image:
    """Stella dello sconto, ruotata come un bollino adesivo."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c, r_out, r_in, n = size / 2, size * 0.49, size * 0.42, 18
    pts = []
    for i in range(n * 2):
        r = r_out if i % 2 == 0 else r_in
        a = math.pi * i / n
        pts.append((c + r * math.cos(a), c + r * math.sin(a)))
    d.polygon(pts, fill=color + (255,))
    fg = text_on(color)
    label = f"-{pct}%"
    f = font(int(size * 0.27), True)
    while f.getlength(label) > size * 0.66 and f.size > 8:
        f = font(f.size - 2, True)
    d.text((c, c), label, font=f, fill=fg, anchor="mm")
    return img.rotate(-10, resample=Image.BICUBIC)


def old_price_line(cents: int, size: int, color: tuple[int, int, int]) -> Image.Image:
    euros, dec = price_parts(cents)
    f = font(size)
    lead, txt = "invece di ", f"€ {euros},{dec}"
    w = int(f.getlength(lead + txt)) + 6
    img = Image.new("RGBA", (w, int(size * 1.35)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((0, 0), lead + txt, font=f, fill=color + (255,))
    x0 = f.getlength(lead)
    y = int(size * 0.62)
    d.line((x0 - 2, y, w - 2, y), fill=color + (255,), width=max(2, size // 11))
    return img


def pill(text: str, size: int, bg: tuple[int, int, int], fg: tuple[int, int, int] | None = None,
         outline: bool = False) -> Image.Image:
    f = font(size, True)
    w, h = int(f.getlength(text) + size * 1.1), int(size * 1.7)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if outline:
        d.rounded_rectangle((1, 1, w - 2, h - 2), radius=h // 2, outline=bg + (255,), width=max(2, size // 9))
        d.text((w / 2, h / 2), text, font=f, fill=(fg or bg) + (255,), anchor="mm")
    else:
        d.rounded_rectangle((0, 0, w - 1, h - 1), radius=h // 2, fill=bg + (255,))
        d.text((w / 2, h / 2), text, font=f, fill=(fg or text_on(bg)) + (255,), anchor="mm")
    return img


def load_rgba(path: str | None) -> Image.Image | None:
    if not path or not Path(path).exists():
        return None
    try:
        with Image.open(path) as im:
            return im.convert("RGBA")
    except OSError:
        return None


def is_cutout(img: Image.Image) -> bool:
    lo = img.getchannel("A").getextrema()[0]
    return lo < 128


def product_visual(path: str | None, max_w: int, max_h: int, brand: tuple[int, int, int], u: float,
                   fallback_text: str = "") -> Image.Image:
    """Il prodotto pronto da mettere in scena: scontornato con ombra, oppure in una cornice."""
    img = load_rgba(path)
    canvas = Image.new("RGBA", (max_w, max_h), (0, 0, 0, 0))
    if img is None:
        # Nessuna foto: un riquadro elegante con il nome, invece di un buco.
        d = ImageDraw.Draw(canvas)
        side = int(min(max_w, max_h) * 0.78)
        x0, y0 = (max_w - side) / 2, (max_h - side) / 2
        d.rounded_rectangle((x0, y0, x0 + side, y0 + side), radius=int(side * 0.12),
                            fill=mix(brand, WHITE, 0.82) + (255,))
        if fallback_text:
            f, lines = fit_text(fallback_text, int(side * 0.8), int(side * 0.7), int(side * 0.16), True, 4)
            lay = text_layer(lines, f, readable_on_paper(brand), "center")
            canvas.alpha_composite(lay, (int((max_w - lay.width) / 2), int((max_h - lay.height) / 2)))
        return canvas
    if is_cutout(img):
        img.thumbnail((int(max_w * 0.92), int(max_h * 0.86)), Image.LANCZOS)
        if img.width < max_w * 0.5 and img.height < max_h * 0.5:      # piccola: si ingrandisce
            s = min(max_w * 0.8 / img.width, max_h * 0.75 / img.height)
            img = img.resize((int(img.width * s), int(img.height * s)), Image.LANCZOS)
        # Podio: ellisse di luce sotto il prodotto.
        d = ImageDraw.Draw(canvas)
        pw = img.width * 1.05
        cx, base = max_w / 2, (max_h + img.height) / 2
        d.ellipse((cx - pw / 2, base - 22 * u, cx + pw / 2, base + 30 * u), fill=INK + (40,))
        canvas = canvas.filter(ImageFilter.GaussianBlur(14 * u))
        sh = shadow_of(img, 18 * u, 0.28)
        canvas.alpha_composite(sh, (int((max_w - sh.width) / 2 + 10 * u), int((max_h - sh.height) / 2 + 22 * u)))
        canvas.alpha_composite(img, (int((max_w - img.width) / 2), int((max_h - img.height) / 2)))
        return canvas
    # Foto intera: cornice bianca arrotondata con ombra.
    border = int(16 * u)
    img.thumbnail((max_w - 2 * border - int(40 * u), max_h - 2 * border - int(40 * u)), Image.LANCZOS)
    card = Image.new("RGBA", (img.width + 2 * border, img.height + 2 * border), WHITE + (255,))
    card.alpha_composite(img, (border, border))
    mask = Image.new("L", card.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, card.width - 1, card.height - 1), radius=int(28 * u), fill=255)
    card.putalpha(mask)
    sh = shadow_of(card, 22 * u, 0.25)
    canvas.alpha_composite(sh, (int((max_w - sh.width) / 2), int((max_h - sh.height) / 2 + 16 * u)))
    canvas.alpha_composite(card, (int((max_w - card.width) / 2), int((max_h - card.height) / 2)))
    return canvas


def logo_image(path: str | None, max_w: int, max_h: int, on: tuple[int, int, int]) -> Image.Image | None:
    """Logo del negozio, su un fondino bianco se il fondo dietro è scuro o colorato."""
    img = load_rgba(path)
    if img is None:
        return None
    img.thumbnail((max_w, max_h), Image.LANCZOS)
    if luminance(on) > 0.75:
        return img
    pad = int(max(8, min(img.width, img.height) * 0.12))
    plate = Image.new("RGBA", (img.width + 2 * pad, img.height + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(plate).rounded_rectangle((0, 0, plate.width - 1, plate.height - 1),
                                            radius=int(pad * 1.4), fill=WHITE + (245,))
    plate.alpha_composite(img, (pad, pad))
    return plate


def qr_image(data: str, size: int) -> Image.Image | None:
    if not data:
        return None
    try:
        import segno
    except ImportError:
        return None
    buf = io.BytesIO()
    segno.make(data, error="m").save(buf, kind="png", scale=10, border=2, dark="#141b2d", light="#ffffff")
    buf.seek(0)
    with Image.open(buf) as im:
        return im.convert("RGBA").resize((size, size), Image.NEAREST)


# ---------------------------------------------------------------- scene

class Renderer:
    def __init__(self, spec: VideoSpec):
        if spec.format not in FORMATS:
            raise RenderError(f"Formato sconosciuto: {spec.format}")
        self.spec = spec
        w, h = FORMATS[spec.format]
        self.W, self.H = int(w * spec.scale) // 2 * 2, int(h * spec.scale) // 2 * 2
        self.u = min(self.W, self.H) / 1080
        self.brand = hex_rgb(spec.brand_color)
        self.accent = hex_rgb(spec.accent_color)
        self.brand_text = readable_on_paper(self.brand)
        self.portrait = self.H > self.W * 1.2
        self.square = not self.portrait and self.W < self.H * 1.3
        self.stacked = self.portrait or self.square      # nome e periodo su due righe
        self.header_h = int(self.u * (150 if self.portrait else 140 if self.square else 112))
        self._soft = None
        self.scenes = self._build_scenes()
        self.total_frames = sum(n for _, n, _ in self.scenes)

    def _n(self, seconds: float) -> int:
        return max(2, int(round(seconds * self.spec.fps)))

    def _build_scenes(self):
        scenes = [(self._intro(), self._n(self.spec.intro_seconds), "intro")]
        for i, offer in enumerate(self.spec.offers):
            scenes.append((self._offer_scene(offer, i), self._n(self.spec.offer_seconds), "offer"))
        scenes.append((self._outro(), self._n(self.spec.outro_seconds), "outro"))
        return scenes

    # -- elementi ricorrenti

    def soft(self) -> Image.Image:
        if self._soft is None:
            self._soft = soft_background(self.W, self.H, self.brand, self.u)
        return self._soft

    def _header(self, bg: Image.Image) -> None:
        u, d = self.u, ImageDraw.Draw(bg)
        d.rectangle((0, 0, self.W, self.header_h), fill=self.brand + (255,))
        fg = text_on(self.brand)
        margin = 46 * u
        x = margin
        logo = logo_image(self.spec.logo_path, int(260 * u), int(self.header_h * 0.62), self.brand)
        if logo is not None:
            bg.alpha_composite(logo, (int(x), int((self.header_h - logo.height) / 2)))
            x += logo.width + 22 * u
        name_w = int(self.W - x - margin)
        if self.stacked:
            f, lines = fit_text(self.spec.store_name, name_w, int(56 * u), int(46 * u), True, 1)
            top = self.header_h / 2 - (32 * u if self.spec.validity else 0)
            d.text((x, top), lines[0] if lines else "", font=f, fill=fg, anchor="lm")
            if self.spec.validity:
                fv, lv = fit_text(self.spec.validity, name_w, int(40 * u), int(30 * u), False, 1)
                d.text((x, self.header_h / 2 + 30 * u), lv[0] if lv else "", font=fv, fill=fg, anchor="lm")
        else:
            fv = font(int(28 * u))
            val_w = fv.getlength(self.spec.validity) if self.spec.validity else 0
            f, lines = fit_text(self.spec.store_name, int(name_w - val_w - 40 * u), int(56 * u), int(44 * u), True, 1)
            d.text((x, self.header_h / 2), lines[0] if lines else "", font=f, fill=fg, anchor="lm")
            if self.spec.validity:
                d.text((self.W - margin, self.header_h / 2), self.spec.validity, font=fv, fill=fg, anchor="rm")

    def _footer(self, bg: Image.Image) -> None:
        if not self.spec.footer_note:
            return
        u = self.u
        f = font(int(20 * u))
        d = ImageDraw.Draw(bg)
        d.text((self.W / 2, self.H - 26 * u), self.spec.footer_note, font=f, fill=(110, 112, 120), anchor="mm")

    def _dots(self, canvas: Image.Image, index: int) -> None:
        n = len(self.spec.offers)
        if n < 2 or n > 24:
            return
        u = self.u
        r, gap = 6 * u, 22 * u
        total = (n - 1) * gap
        x0, y = self.W / 2 - total / 2, self.H - 62 * u
        d = ImageDraw.Draw(canvas)
        for i in range(n):
            x = x0 + i * gap
            if i == index:
                d.rounded_rectangle((x - r * 2.2, y - r, x + r * 2.2, y + r), radius=r, fill=self.brand + (255,))
            else:
                d.ellipse((x - r * 0.8, y - r * 0.8, x + r * 0.8, y + r * 0.8), fill=(190, 186, 176, 255))

    # -- apertura

    def _intro(self):
        u, W, H = self.u, self.W, self.H
        bg = brand_background(W, H, self.brand, self.accent, u)
        fg = text_on(self.brand)
        logo = logo_image(self.spec.logo_path, int(W * 0.5), int(H * (0.18 if self.portrait else 0.24)), self.brand)
        maxw = int(W * 0.84)
        if self.spec.idea_headline:
            # l'idea della settimana in grande, il negozio piccolo sopra (il logo c'è già)
            fs, ls = fit_text(self.spec.store_name, maxw, int(H * 0.08), int(46 * u), False, 1)
            fh, lh = fit_text(self.spec.headline, maxw, int(H * 0.3), int(128 * u), True, 3, min_size=int(48 * u))
        else:
            fs, ls = fit_text(self.spec.store_name, maxw, int(H * 0.22), int(118 * u), True, 2)
            fh, lh = fit_text(self.spec.headline, maxw, int(H * 0.16), int(58 * u), False, 2)
        name = text_layer(ls, fs, fg, "center")
        head = text_layer(lh, fh, fg, "center")
        val = pill(self.spec.validity, int(38 * u), self.accent) if self.spec.validity else None
        blocks = [b for b in (logo, name, head) if b is not None]
        gap = 34 * u
        total = sum(b.height for b in blocks) + gap * (len(blocks) - 1) + ((val.height + 60 * u) if val else 0)
        y0 = (H - total) / 2

        def draw(t: float) -> Image.Image:
            c = bg.copy()
            y = y0
            k = 0
            for blk in blocks:
                p = ease_back((t - 0.06 - k * 0.12) / 0.32, 1.3) if blk is logo else ease_out((t - 0.06 - k * 0.12) / 0.3)
                if p > 0:
                    s = 0.6 + 0.4 * min(p, 1.1) if blk is logo else 1.0
                    paste_center(c, blk, W / 2, y + blk.height / 2 + (1 - min(p, 1)) * 50 * u, s, min(1.0, p * 1.4))
                y += blk.height + gap
                k += 1
            if val is not None:
                p = ease_back((t - 0.42) / 0.25)
                if p > 0:
                    paste_center(c, val, W / 2, y + 26 * u + val.height / 2, max(0.05, p))
            if t > 0.9:
                c.alpha_composite(Image.new("RGBA", (W, H), self.brand + (int(255 * ease_in((t - 0.9) / 0.1) * 0.55),)))
            return c
        return draw

    # -- offerta

    def _layout(self, stacked: bool | None = None):
        u, W, H = self.u, self.W, self.H
        top, bottom = self.header_h + 30 * u, H - 90 * u
        if self.portrait if stacked is None else stacked:
            img_box = (int(W * 0.9), int((bottom - top) * 0.5))
            img_xy = ((W - img_box[0]) / 2, top)
            text_x, text_w = W * 0.08, int(W * 0.84)
            text_top, text_bottom = top + img_box[1] + 20 * u, bottom - 30 * u
        else:
            split = 0.5 if self.square else 0.52
            img_box = (int(W * split - 60 * u), int(bottom - top))
            img_xy = (40 * u, top)
            text_x, text_w = W * split + 10 * u, int(W * (1 - split) - 70 * u)
            text_top, text_bottom = top, bottom - 30 * u
        return img_box, img_xy, text_x, text_w, text_top, text_bottom

    def _offer_scene(self, o: VideoOffer, index: int):
        u = self.u
        bg = self.soft().copy()
        self._header(bg)
        self._footer(bg)
        # Nel quadrato una foto larga (pesce nel piatto, salame sul tagliere) va sopra, a tutta larghezza.
        wide = False
        if self.square and o.image_path:
            try:
                with Image.open(o.image_path) as im:
                    wide = im.width >= im.height * 1.3
            except OSError:
                wide = False
        stacked = self.portrait or wide
        img_box, img_xy, text_x, text_w, text_top, text_bottom = self._layout(stacked)
        sq = 0.82 if self.square else 1.0
        if wide:
            sq = 0.7

        brand_l = None
        if o.brand and o.brand.lower() not in o.name.lower():
            brand_l = text_layer([o.brand.upper()], font(int(30 * u * sq), True), self.brand_text)
        fn, ln = fit_text(o.name, text_w, int(220 * u * sq), int(74 * u * sq), True, 3, min_size=int(26 * u))
        name = text_layer(ln, fn, INK)
        desc = None
        if o.description:
            fd, ld = fit_text(o.description, text_w, int(90 * u), int(38 * u * sq), False, 2)
            desc = text_layer(ld, fd, (88, 92, 104))
        price = price_block(o.price_cents, int(200 * u * sq), self.brand)
        if price.width > text_w:
            price = scaled(price, text_w / price.width)
        old = old_price_line(o.old_price_cents, int(36 * u * sq), (96, 98, 108)) if o.old_price_cents else None
        unit = text_layer([o.unit_price_text], font(int(26 * u * sq)), (110, 112, 120)) if o.unit_price_text else None
        cond = pill(o.conditions[:60], int(26 * u * sq), self.brand_text, outline=True) if o.conditions else None
        if cond is not None and cond.width > text_w:
            cond = scaled(cond, text_w / cond.width)
        burst = discount_burst(o.discount_percent, int(190 * u * sq), self.accent) if o.discount_percent else None

        items = [x for x in (brand_l, name, desc) if x is not None]
        gap_s, gap_m = 8 * u, 26 * u
        block_h = sum(x.height for x in items) + gap_s * (len(items) - 1) + gap_m + price.height
        extras = [x for x in (old, unit, cond) if x is not None]
        block_h += sum(x.height + gap_s * 1.5 for x in extras)
        if stacked:
            # In verticale il prodotto occupa tutto lo spazio che il testo lascia libero.
            avail = text_bottom - img_xy[1]
            img_h = int(min(avail - block_h - 40 * u, avail * 0.66))
            img_box = (img_box[0], max(int(avail * 0.35), img_h))
            spare = max(0.0, avail - (img_box[1] + 30 * u + block_h))
            img_xy = (img_xy[0], img_xy[1] + spare * 0.45)          # gruppo centrato in verticale
            text_top = img_xy[1] + img_box[1] + 30 * u
            y = text_top
        else:
            y = text_top + max(0.0, (text_bottom - text_top - block_h) / 2)
        prod = product_visual(o.image_path, img_box[0], img_box[1], self.brand, u, o.name)
        pos = []
        for x in items:
            pos.append((x, y))
            y += x.height + gap_s
        y += gap_m - gap_s
        price_y = y
        y += price.height + gap_s * 1.5
        extra_pos = []
        for x in extras:
            extra_pos.append((x, y))
            y += x.height + gap_s * 1.5
        prod_cx, prod_cy = img_xy[0] + img_box[0] / 2, img_xy[1] + img_box[1] / 2
        burst_xy = (img_xy[0] + img_box[0] * 0.80, img_xy[1] + img_box[1] * 0.16)

        def draw(t: float) -> Image.Image:
            c = bg.copy()
            out = ease_in((t - 0.9) / 0.1)            # uscita
            dx = -out * 160 * u
            alpha_out = 1 - out
            # Prodotto: entra dal basso e poi zoom lento.
            p = ease_out(t / 0.22)
            zoom = 0.92 + 0.08 * p + 0.035 * max(0.0, t - 0.22)
            paste_center(c, prod, prod_cx + dx, prod_cy + (1 - p) * 120 * u, zoom, min(p * 1.3, 1) * alpha_out)
            # Testi.
            for k, (lay, ly) in enumerate(pos):
                q = ease_out((t - 0.08 - k * 0.04) / 0.2)
                paste(c, lay, text_x + (1 - q) * 90 * u + dx, ly, q * alpha_out)
            # Prezzo: "pop" con rimbalzo.
            q = ease_back((t - 0.2) / 0.18)
            if q > 0:
                s = max(0.05, q)
                lay = scaled(price, s)
                paste(c, lay, text_x + (price.width - lay.width) / 2 + dx, price_y + (price.height - lay.height) / 2,
                      alpha_out)
            for k, (lay, ly) in enumerate(extra_pos):
                q = ease_out((t - 0.32 - k * 0.04) / 0.18)
                paste(c, lay, text_x + dx, ly + (1 - q) * 20 * u, q * alpha_out)
            if burst is not None:
                q = ease_back((t - 0.3) / 0.2, 2.2)
                if q > 0:
                    wob = 1 + 0.03 * math.sin(max(0.0, t - 0.5) * 18) * max(0.0, 1 - (t - 0.5) * 3)
                    paste_center(c, burst, burst_xy[0] + dx, burst_xy[1], max(0.05, q) * wob, alpha_out)
            self._dots(c, index)
            return c
        return draw

    # -- chiusura

    def _outro(self):
        u, W, H = self.u, self.W, self.H
        bg = brand_background(W, H, self.brand, self.accent, u)
        fg = text_on(self.brand)
        maxw = int(W * 0.84)
        logo = logo_image(self.spec.logo_path, int(W * 0.34), int(H * 0.12), self.brand)
        f1, l1 = fit_text("Ti aspettiamo!", maxw, int(H * 0.16), int(104 * u), True, 1)
        title = text_layer(l1, f1, fg, "center")
        lines = [self.spec.store_name] + ([self.spec.address] if self.spec.address else [])
        f2, l2 = fit_text(" · ".join(lines), maxw, int(H * 0.14), int(44 * u), False, 2)
        addr = text_layer(l2, f2, fg, "center")
        contacts = None
        if self.spec.contact_lines:
            f3, l3 = fit_text("  ·  ".join(self.spec.contact_lines), maxw, int(H * 0.12), int(32 * u), False, 2)
            contacts = text_layer(l3, f3, fg, "center")
        qr = None
        if self.spec.qr_data:
            q = qr_image(self.spec.qr_data, int(min(W, H) * (0.24 if self.portrait else 0.2)))
            if q is not None:
                label = self.spec.qr_label or "Inquadra il codice"
                fl = font(int(24 * u), True)
                pad = int(18 * u)
                lw = int(fl.getlength(label))
                card = Image.new("RGBA", (max(q.width, lw) + 2 * pad, q.height + 2 * pad + int(42 * u)), (0, 0, 0, 0))
                ImageDraw.Draw(card).rounded_rectangle((0, 0, card.width - 1, card.height - 1), radius=int(26 * u),
                                                       fill=WHITE + (255,))
                card.alpha_composite(q, ((card.width - q.width) // 2, pad))
                ImageDraw.Draw(card).text((card.width / 2, q.height + pad + 22 * u), label, font=fl, fill=INK, anchor="mm")
                qr = card
        val = pill(f"Offerte valide {self.spec.validity}", int(32 * u), self.accent) if self.spec.validity else None
        blocks = [b for b in (logo, title, addr, contacts, qr, val) if b is not None]
        gap = 30 * u
        total = sum(b.height for b in blocks) + gap * (len(blocks) - 1)
        if total > H * 0.9:          # troppo alto (es. quadrato con QR): QR più piccolo
            if qr is not None:
                blocks.remove(qr)
                qr = scaled(qr, 0.7)
                blocks.insert(blocks.index(val) if val in blocks else len(blocks), qr)
            total = sum(b.height for b in blocks) + gap * (len(blocks) - 1)
        y0 = (H - total) / 2

        def draw(t: float) -> Image.Image:
            c = bg.copy()
            if t < 0.12:
                c.alpha_composite(Image.new("RGBA", (W, H), self.brand + (int(255 * (1 - t / 0.12) * 0.55),)))
            y = y0
            for k, blk in enumerate(blocks):
                p = ease_out((t - 0.05 - k * 0.07) / 0.25)
                if blk is qr or blk is val:
                    p = ease_back((t - 0.05 - k * 0.07) / 0.25)
                if p > 0:
                    paste_center(c, blk, W / 2, y + blk.height / 2 + (1 - min(p, 1)) * 40 * u,
                                 max(0.05, min(p, 1.15)) if blk is qr else 1.0, min(1.0, p * 1.4))
                y += blk.height + gap
            return c
        return draw

    # -- uscita

    def scene_starts(self) -> list[float]:
        out, t = [], 0.0
        for _, n, _ in self.scenes:
            out.append(t)
            t += n / self.spec.fps
        return out

    def pop_times(self) -> list[float]:
        out = []
        for (_, n, kind), start in zip(self.scenes, self.scene_starts()):
            if kind == "offer":
                out.append(start + 0.2 * n / self.spec.fps + 0.05)
        return out

    def frames(self):
        for draw, n, _ in self.scenes:
            for i in range(n):
                yield draw(i / max(1, n - 1)).convert("RGB")

    def frame_at(self, seconds: float) -> Image.Image:
        idx = int(seconds * self.spec.fps)
        for draw, n, _ in self.scenes:
            if idx < n:
                return draw(idx / max(1, n - 1)).convert("RGB")
            idx -= n
        draw, n, _ = self.scenes[-1]
        return draw(1.0).convert("RGB")

    @property
    def duration(self) -> float:
        return self.total_frames / self.spec.fps


def render_video(spec: VideoSpec, out_path: Path, crf: int = 20, preset: str = "medium") -> Path:
    if not spec.offers:
        raise RenderError("Nessuna offerta da mostrare nel video.")
    ffmpeg = ffmpeg_path()
    r = Renderer(spec)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".part.mp4")
    with tempfile.TemporaryDirectory() as td:
        audio_args: list[str] = []
        if spec.music:
            from .music import compose, write_wav
            wav = write_wav(compose(r.duration, r.scene_starts()[1:], r.pop_times()), Path(td) / "musica.wav")
            audio_args = ["-i", str(wav)]
        cmd = [ffmpeg, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
               "-s", f"{r.W}x{r.H}", "-r", str(spec.fps), "-i", "-", *audio_args,
               "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p"]
        if audio_args:
            cmd += ["-map", "0:v", "-map", "1:a", "-c:a", "aac", "-b:a", "160k", "-shortest"]
        cmd += ["-movflags", "+faststart", str(tmp)]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            assert proc.stdin is not None
            for frame in r.frames():
                proc.stdin.write(frame.tobytes())
            proc.stdin.close()
            err = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
            code = proc.wait()
        except BrokenPipeError:
            err = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
            proc.wait()
            tmp.unlink(missing_ok=True)
            raise RenderError(f"ffmpeg si è interrotto: {err.strip()[:500]}")
        except BaseException:
            proc.kill()
            proc.wait()
            tmp.unlink(missing_ok=True)
            raise
    if code != 0:
        tmp.unlink(missing_ok=True)
        raise RenderError(f"ffmpeg ha restituito un errore: {err.strip()[:500]}")
    tmp.replace(out_path)
    return out_path


def ffmpeg_path() -> str:
    """ffmpeg del sistema; altrimenti quello incluso nel pacchetto imageio-ffmpeg (Windows e Mac)."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # pacchetto assente o binario non disponibile
        raise RenderError("ffmpeg non è installato.") from exc


def probe_duration(path: Path) -> float:
    """Durata reale del file video (secondi): con ffprobe se c'è, altrimenti leggendola da ffmpeg."""
    ffprobe = shutil.which("ffprobe")
    if ffprobe is not None:
        out = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration", "-of",
                              "default=noprint_wrappers=1:nokey=1", str(path)], capture_output=True, text=True)
        try:
            value = float(out.stdout.strip())
            if not math.isnan(value):
                return value
        except ValueError:
            pass
    info = subprocess.run([ffmpeg_path(), "-hide_banner", "-i", str(path)], capture_output=True, text=True)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", info.stderr)
    if not m:
        raise RenderError("Durata del video non leggibile.")
    h, mnt, sec = m.groups()
    return int(h) * 3600 + int(mnt) * 60 + float(sec)
