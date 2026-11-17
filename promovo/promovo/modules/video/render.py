"""Agente "Montatore": video promozionale generico per qualsiasi volantino.

Formati: orizzontale 16:9 (schermi in negozio) e verticale 9:16 (Reel, Storie, TikTok).
Scene: apertura con il negozio, una scena per ogni offerta, chiusura con indirizzo e validità.
I fotogrammi sono disegnati con Pillow e codificati in H.264 da ffmpeg.
"""
from __future__ import annotations

import math
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from ...money import price_parts

FONT_DIR = Path(__file__).resolve().parents[2] / "assets" / "fonts"

FORMATS = {
    "landscape": (1920, 1080),
    "portrait": (1080, 1920),
    "square": (1080, 1080),
}


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
    intro_seconds: float = 3.0
    offer_seconds: float = 3.5
    outro_seconds: float = 4.0
    scale: float = 1.0                  # <1 per anteprime veloci
    footer_note: str = "Offerte valide fino a esaurimento scorte. Le foto sono indicative."
    warnings: list[str] = field(default_factory=list)


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
    return (20, 24, 33) if luminance(bg) > 0.4 else (255, 255, 255)


@lru_cache(maxsize=64)
def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return ImageFont.truetype(str(FONT_DIR / name), max(8, int(size)))


def wrap(text: str, fnt: ImageFont.FreeTypeFont, max_width: int, max_lines: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if fnt.getlength(trial) <= max_width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
            while fnt.getlength(cur) > max_width and len(cur) > 1:  # parola troppo lunga
                cut = len(cur)
                while cut > 1 and fnt.getlength(cur[:cut] + "…") > max_width:
                    cut -= 1
                lines.append(cur[:cut] + "…")
                cur = ""
                break
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
        total = len(lines) * int(size * 1.18)
        if total <= max_height and all(f.getlength(line) <= max_width for line in lines):
            return f, lines
        size = int(size * 0.92)
    f = font(min_size, bold)
    return f, wrap(text, f, max_width, max_lines)


def text_layer(lines: list[str], fnt: ImageFont.FreeTypeFont, color: tuple[int, int, int],
               align: str = "left", line_gap: float = 1.18) -> Image.Image:
    lh = int(fnt.size * line_gap)
    width = max((int(fnt.getlength(line)) for line in lines), default=1) + 4
    img = Image.new("RGBA", (max(width, 1), max(lh * len(lines), 1)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        w = fnt.getlength(line)
        x = 0 if align == "left" else (width - w) / 2 if align == "center" else width - w
        d.text((x, i * lh), line, font=fnt, fill=color + (255,))
    return img


def ease_out(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def ease_back(x: float, s: float = 1.6) -> float:
    x = min(max(x, 0.0), 1.0) - 1
    return 1 + (s + 1) * x ** 3 + s * x ** 2


def with_alpha(img: Image.Image, alpha: float) -> Image.Image:
    if alpha >= 0.999:
        return img
    out = img.copy()
    a = out.getchannel("A").point(lambda v: int(v * max(0.0, alpha)))
    out.putalpha(a)
    return out


def paste(canvas: Image.Image, layer: Image.Image, x: float, y: float, alpha: float = 1.0) -> None:
    if alpha <= 0.002:
        return
    canvas.alpha_composite(with_alpha(layer, alpha), (int(round(x)), int(round(y))))


# ---------------------------------------------------------------- elementi

def price_badge(cents: int, size: int, color: tuple[int, int, int]) -> Image.Image:
    """Cartellino del prezzo: euro grandi, centesimi in alto e simbolo € sotto i centesimi."""
    euros, dec = price_parts(cents)
    big = font(int(size * 0.46), True)
    small = font(int(size * 0.2), True)
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    eb = probe.textbbox((0, 0), euros, font=big, anchor="ls")      # top negativo rispetto alla linea base
    db = probe.textbbox((0, 0), f",{dec}", font=small, anchor="lt")
    sb = probe.textbbox((0, 0), "€", font=small, anchor="ls")
    w_euros = eb[2] - eb[0]
    w_right = max(db[2] - db[0], sb[2] - sb[0])
    gap = size * 0.03
    content_w = w_euros + gap + w_right
    width = int(max(size, content_w + size * 0.36))
    img = Image.new("RGBA", (width, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, width - 1, size - 1), radius=int(size * 0.18), fill=color + (255,))
    fg = text_on(color)
    cap = -eb[1]                                    # altezza delle cifre grandi
    baseline = (size + cap) / 2
    x = (width - content_w) / 2 - eb[0]
    d.text((x, baseline), euros, font=big, fill=fg, anchor="ls")
    x2 = x + eb[2] + gap
    d.text((x2, baseline - cap), f",{dec}", font=small, fill=fg, anchor="lt")
    d.text((x2, baseline), "€", font=small, fill=fg, anchor="ls")
    return img


def old_price_layer(cents: int, size: int, color: tuple[int, int, int]) -> Image.Image:
    euros, dec = price_parts(cents)
    f = font(size)
    txt = f"invece di € {euros},{dec}"
    w = int(f.getlength(txt)) + 4
    img = Image.new("RGBA", (w, int(size * 1.3)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((0, 0), txt, font=f, fill=color + (255,))
    start = f.getlength("invece di ")
    yline = int(size * 0.62)
    d.line((start, yline, w - 2, yline), fill=color + (255,), width=max(2, size // 12))
    return img


def tag_layer(text: str, size: int, bg: tuple[int, int, int]) -> Image.Image:
    f = font(size, True)
    w = int(f.getlength(text) + size * 1.0)
    h = int(size * 1.6)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=h // 2, fill=bg + (255,))
    d.text((size * 0.5, size * 0.22), text, font=f, fill=text_on(bg))
    return img


def product_image(path: str | None, max_w: int, max_h: int) -> Image.Image:
    box = Image.new("RGBA", (max_w, max_h), (0, 0, 0, 0))
    if path and Path(path).exists():
        try:
            with Image.open(path) as src:
                im = src.convert("RGBA")
        except OSError:
            im = None
        if im is not None:
            im.thumbnail((max_w - 24, max_h - 24), Image.LANCZOS)
            card = Image.new("RGBA", (im.width + 24, im.height + 24), (255, 255, 255, 255))
            mask = Image.new("L", card.size, 0)
            ImageDraw.Draw(mask).rounded_rectangle((0, 0, card.width - 1, card.height - 1), radius=22, fill=255)
            card.paste(im, (12, 12))
            card.putalpha(mask)
            shadow = Image.new("RGBA", (card.width + 30, card.height + 30), (0, 0, 0, 0))
            ImageDraw.Draw(shadow).rounded_rectangle((15, 22, card.width + 15, card.height + 22),
                                                     radius=26, fill=(0, 0, 0, 60))
            shadow.alpha_composite(card, (15, 15))
            shadow.thumbnail((max_w, max_h), Image.LANCZOS)
            box.alpha_composite(shadow, ((max_w - shadow.width) // 2, (max_h - shadow.height) // 2))
            return box
    d = ImageDraw.Draw(box)
    d.rounded_rectangle((max_w * 0.1, max_h * 0.1, max_w * 0.9, max_h * 0.9), radius=40,
                        fill=(235, 235, 235, 255))
    return box


# ---------------------------------------------------------------- scene

class Renderer:
    def __init__(self, spec: VideoSpec):
        if spec.format not in FORMATS:
            raise RenderError(f"Formato sconosciuto: {spec.format}")
        self.spec = spec
        w, h = FORMATS[spec.format]
        self.W, self.H = int(w * spec.scale) // 2 * 2, int(h * spec.scale) // 2 * 2
        self.u = min(self.W, self.H) / 1080          # unità di misura proporzionale
        self.brand = hex_rgb(spec.brand_color)
        self.accent = hex_rgb(spec.accent_color)
        self.paper = (250, 247, 240)
        self.ink = (28, 31, 40)
        self.portrait = self.H > self.W
        self.header_h = int(self.u * 120)
        self.scenes = self._build_scenes()
        self.total_frames = sum(n for _, n in self.scenes)

    # -- costruzione

    def _n(self, seconds: float) -> int:
        return max(1, int(round(seconds * self.spec.fps)))

    def _build_scenes(self):
        scenes = [(self._intro(), self._n(self.spec.intro_seconds))]
        for i, offer in enumerate(self.spec.offers):
            scenes.append((self._offer_scene(offer, i), self._n(self.spec.offer_seconds)))
        scenes.append((self._outro(), self._n(self.spec.outro_seconds)))
        return scenes

    def _background(self, color: tuple[int, int, int], band: bool) -> Image.Image:
        bg = Image.new("RGBA", (self.W, self.H), color + (255,))
        d = ImageDraw.Draw(bg)
        if band:
            fg = text_on(self.brand)
            margin = self.u * 50
            fv = font(int(self.u * 30))
            val_w = fv.getlength(self.spec.validity) if self.spec.validity else 0
            f, name_lines = fit_text(self.spec.store_name, int(self.W - 2 * margin), int(self.u * 60),
                                     int(self.u * 46), True, 1)
            name_w = f.getlength(name_lines[0]) if name_lines else 0
            one_row = name_w + val_w + self.u * 40 <= self.W - 2 * margin
            bh = self.header_h = int(self.u * (120 if one_row or not self.spec.validity else 160))
            d.rectangle((0, 0, self.W, bh), fill=self.brand + (255,))
            d.text((margin, self.u * 34), name_lines[0] if name_lines else "", font=f, fill=fg)
            if self.spec.validity:
                if one_row:
                    d.text((self.W - val_w - margin, self.u * 46), self.spec.validity, font=fv, fill=fg)
                else:
                    d.text((margin, self.u * 100), self.spec.validity, font=fv, fill=fg)
            fh = int(self.u * 56)
            d.rectangle((0, self.H - fh, self.W, self.H), fill=(235, 230, 220, 255))
            fn = font(int(self.u * 22))
            note = self.spec.footer_note
            d.text(((self.W - fn.getlength(note)) / 2, self.H - fh + self.u * 16), note, font=fn, fill=(90, 90, 90))
        return bg

    def _intro(self):
        bg = self._background(self.brand, band=False)
        fg = text_on(self.brand)
        maxw = int(self.W * 0.84)
        fs, ls = fit_text(self.spec.store_name, maxw, int(self.H * 0.3), int(self.u * 130), True, 2)
        name = text_layer(ls, fs, fg, "center")
        fh, lh = fit_text(self.spec.headline, maxw, int(self.H * 0.2), int(self.u * 64), False, 2)
        head = text_layer(lh, fh, fg, "center")
        val = tag_layer(self.spec.validity, int(self.u * 40), self.accent) if self.spec.validity else None

        def draw(t: float) -> Image.Image:
            c = bg.copy()
            cy = self.H * 0.36
            p1 = ease_out(t / 0.35)
            paste(c, name, (self.W - name.width) / 2, cy - name.height / 2 + (1 - p1) * self.u * 80, p1)
            p2 = ease_out((t - 0.2) / 0.35)
            paste(c, head, (self.W - head.width) / 2, cy + name.height / 2 + self.u * 40 + (1 - p2) * self.u * 60, p2)
            if val is not None:
                p3 = ease_back((t - 0.4) / 0.3)
                if p3 > 0:
                    sc = max(0.05, p3)
                    v = val.resize((max(1, int(val.width * sc)), max(1, int(val.height * sc))), Image.BILINEAR)
                    paste(c, v, (self.W - v.width) / 2, self.H * 0.72 - v.height / 2)
            return c
        return draw

    def _offer_scene(self, o: VideoOffer, index: int):
        bg = self._background(self.paper, band=True)
        top, bottom = self.header_h + self.u * 30, self.H - self.u * 80
        text_w = int(self.W * 0.84) if self.portrait else int(self.W * 0.42)

        fn, ln = fit_text(o.name, text_w, int(self.u * 230), int(self.u * 76), True, 3)
        name = text_layer(ln, fn, self.ink)
        desc = None
        if o.description:
            fd, ld = fit_text(o.description, text_w, int(self.u * 90), int(self.u * 40), False, 2)
            desc = text_layer(ld, fd, (85, 88, 98))
        badge = price_badge(o.price_cents, int(self.u * 230), self.brand)
        old = old_price_layer(o.old_price_cents, int(self.u * 40), (95, 95, 95)) if o.old_price_cents else None
        disc = tag_layer(f"-{o.discount_percent}%", int(self.u * 52), self.accent) if o.discount_percent else None
        cond = None
        if o.conditions:
            fc, lc = fit_text(o.conditions, text_w, int(self.u * 80), int(self.u * 32), True, 2)
            cond = text_layer(lc, fc, self.brand)

        # Altezza del blocco di testo, poi tutto viene centrato nello spazio disponibile.
        gap_s, gap_m = self.u * 10, self.u * 24
        block = name.height + gap_s
        if desc:
            block += desc.height + gap_m
        block += badge.height
        if old:
            block += gap_s + old.height
        if cond:
            block += gap_s + cond.height

        if self.portrait:
            img_h = int(max(self.u * 300, (bottom - top) - block - self.u * 60))
            img_box = (int(self.W * 0.86), img_h)
            content_h = img_h + self.u * 40 + block
            y0 = top + max(0.0, ((bottom - top) - content_h) / 2)
            img_pos = ((self.W - img_box[0]) / 2, y0)
            text_x, text_y = self.W * 0.08, y0 + img_h + self.u * 40
        else:
            img_box = (int(self.W * 0.46), int(bottom - top - self.u * 20))
            img_pos = (self.W * 0.04, top)
            text_x = self.W * 0.54
            text_y = top + max(0.0, ((bottom - top) - block) / 2)

        prod = product_image(o.image_path, *img_box)
        y = text_y
        pos_name = y
        y += name.height + gap_s
        pos_desc = y
        if desc:
            y += desc.height + gap_m
        pos_badge = y
        y += badge.height
        pos_old = y + gap_s
        if old:
            y += gap_s + old.height
        pos_cond = y + gap_s

        def draw(t: float) -> Image.Image:
            c = bg.copy()
            p = ease_out(t / 0.22)
            paste(c, prod, img_pos[0] - (1 - p) * self.u * 120, img_pos[1], p)
            p = ease_out((t - 0.08) / 0.22)
            paste(c, name, text_x + (1 - p) * self.u * 80, pos_name, p)
            if desc:
                paste(c, desc, text_x + (1 - p) * self.u * 80, pos_desc, p)
            pb = ease_back((t - 0.18) / 0.2)
            if pb > 0:
                sc = max(0.05, pb)
                b = badge if abs(sc - 1) < 0.01 else badge.resize(
                    (max(1, int(badge.width * sc)), max(1, int(badge.height * sc))), Image.BILINEAR)
                paste(c, b, text_x + (badge.width - b.width) / 2, pos_badge + (badge.height - b.height) / 2)
            pt = ease_out((t - 0.3) / 0.2)
            if old:
                paste(c, old, text_x, pos_old, pt)
            if disc:
                paste(c, disc, text_x + badge.width + self.u * 24, pos_badge + (badge.height - disc.height) / 2, pt)
            if cond:
                paste(c, cond, text_x, pos_cond, pt)
            # Uscita morbida negli ultimi istanti della scena.
            if t > 0.92:
                fade = Image.new("RGBA", c.size, self.paper + (int(255 * (t - 0.92) / 0.08 * 0.6),))
                c.alpha_composite(fade)
            return c
        return draw

    def _outro(self):
        bg = self._background(self.brand, band=False)
        fg = text_on(self.brand)
        maxw = int(self.W * 0.84)
        f1, l1 = fit_text("Ti aspettiamo!", maxw, int(self.H * 0.2), int(self.u * 110), True, 1)
        title = text_layer(l1, f1, fg, "center")
        lines = [self.spec.store_name]
        if self.spec.address:
            lines.append(self.spec.address)
        f2, l2 = fit_text(" · ".join(lines), maxw, int(self.H * 0.2), int(self.u * 50), False, 3)
        addr = text_layer(l2, f2, fg, "center")
        val = tag_layer(f"Offerte valide {self.spec.validity}", int(self.u * 38), self.accent) \
            if self.spec.validity else None

        def draw(t: float) -> Image.Image:
            c = bg.copy()
            p = ease_out(t / 0.3)
            paste(c, title, (self.W - title.width) / 2, self.H * 0.3 + (1 - p) * self.u * 60, p)
            p = ease_out((t - 0.15) / 0.3)
            paste(c, addr, (self.W - addr.width) / 2, self.H * 0.3 + title.height + self.u * 50, p)
            if val is not None:
                p = ease_out((t - 0.3) / 0.3)
                paste(c, val, (self.W - val.width) / 2, self.H * 0.72, p)
            return c
        return draw

    # -- uscita

    def frames(self):
        for draw, n in self.scenes:
            for i in range(n):
                yield draw(i / max(1, n - 1)).convert("RGB")

    def frame_at(self, seconds: float) -> Image.Image:
        idx = int(seconds * self.spec.fps)
        for draw, n in self.scenes:
            if idx < n:
                return draw(idx / max(1, n - 1)).convert("RGB")
            idx -= n
        draw, n = self.scenes[-1]
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
    cmd = [ffmpeg, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{r.W}x{r.H}", "-r", str(spec.fps), "-i", "-",
           "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p",
           "-movflags", "+faststart", str(tmp)]
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
