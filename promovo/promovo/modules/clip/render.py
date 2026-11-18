"""Montatore dei video "dal banco": dai tratti scelti al Reel 9:16 finito.

1. Taglia i tratti migliori, li raddrizza in verticale (9:16) e li stabilizza (vidstab, se c'è).
2. Li unisce con il rumore vero del negozio, abbassato.
3. Sovrappone la grafica disegnata fotogramma per fotogramma: logo e nome del negozio, titolo d'apertura,
   sottotitoli, cartellino con prodotto e prezzo (preso dal volantino, già controllato).
4. Chiude con la scena finale di Promovo (logo, indirizzo, QR code) e mixa musica e voce.
Tutto con l'ffmpeg incluso nel pacchetto, anche su Windows: nessun percorso nei filtri.
"""
from __future__ import annotations

import math
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from ..video.music import SR, compose, write_wav
from ..video.render import (RenderError, Renderer, VideoSpec, ease_back, ease_in, ease_out, ffmpeg_path, fit_text,
                            font, hex_rgb, logo_image, paste, pill, price_block, scaled, text_on)
from .analyze import Segment, VideoInfo

W, H, FPS = 1080, 1920, 30
OUTRO_SECONDS = 2.8
MIN_FOOTAGE, MAX_FOOTAGE = 6.0, 30.0


@dataclass
class ProductCard:
    """Cartellino del prodotto inquadrato in un tratto: dati presi dal volantino, già controllati."""
    product: str
    price_cents: int
    brand: str = ""
    description: str = ""
    unit_text: str = ""
    conditions: str = ""


@dataclass
class ClipText:
    hook: str = ""
    captions: list[str] = field(default_factory=list)
    validity: str = ""
    # Un cartellino per ogni tratto (None = in quel tratto non si mostra nessun prezzo).
    cards: list[ProductCard | None] = field(default_factory=list)
    # Senza voce: un sottotitolo per tratto, mostrato mentre si vede quel tratto.
    segment_lines: list[str] = field(default_factory=list)


@dataclass
class ClipSpec:
    source: Path
    info: VideoInfo
    segments: list[Segment]
    store_name: str
    text: ClipText
    brand_color: str = "#D7262E"
    accent_color: str = "#FFD23F"
    logo_path: str | None = None
    outro: VideoSpec | None = None          # scena finale (indirizzo, contatti, QR)
    voice_path: Path | None = None           # voce fuori campo, già pulita (WAV)
    voice_is_ai: bool = False                # voce sintetica: va dichiarata (AI Act, art. 50)
    music: bool = True
    ambient: bool = True                     # tiene il rumore vero del negozio, basso


# ------------------------------------------------------------------ ffmpeg

@lru_cache(maxsize=4)
def _filters(ffmpeg: str) -> str:
    return subprocess.run([ffmpeg, "-hide_banner", "-filters"], capture_output=True, text=True).stdout


def has_filter(name: str) -> bool:
    return f" {name} " in _filters(ffmpeg_path())


def _run(cmd: list[str], cwd: Path, what: str) -> None:
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    if proc.returncode != 0:
        raise RenderError(f"{what}: {proc.stderr.strip()[-600:]}")


def audio_duration(path: Path) -> float:
    proc = subprocess.run([ffmpeg_path(), "-hide_banner", "-i", str(path)], capture_output=True, text=True)
    import re
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", proc.stderr)
    if not m:
        raise RenderError("Durata dell'audio non riconosciuta.")
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def clean_voice(src: Path, dst: Path) -> float:
    """Voce registrata o sintetica -> WAV mono 48 kHz, senza silenzi ai bordi, volume uniforme.

    Restituisce la durata in secondi."""
    if src.resolve() == dst.resolve():          # ffmpeg non può scrivere sul file che sta leggendo
        raise RenderError("La voce pulita deve andare in un file diverso dall'originale.")
    af = ("silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.1,"
          "areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.15,areverse,"
          "highpass=f=80,loudnorm=I=-16:TP=-1.5:LRA=11")
    _run([ffmpeg_path(), "-y", "-v", "error", "-i", str(src), "-vn", "-af", af, "-ar", "48000", "-ac", "1", dst.name],
         dst.parent, "Voce non leggibile")
    dur = audio_duration(dst)
    if dur < 0.8:
        raise RenderError("La voce registrata è vuota o troppo corta.")
    return dur


def _crop_filter(info: VideoInfo) -> str:
    """Taglio verticale 9:16 al centro; per i video già verticali solo il ridimensionamento."""
    ar = info.width / info.height
    target = W / H
    if ar > target + 0.01:                       # più largo: si tiene il centro
        return f"crop=trunc(ih*{target:.5f}/2)*2:ih,scale={W}:{H}:flags=lanczos"
    if ar < target - 0.01:                       # più stretto (raro): si tiene il centro in altezza
        return f"crop=iw:trunc(iw/{target:.5f}/2)*2,scale={W}:{H}:flags=lanczos"
    return f"scale={W}:{H}:flags=lanczos"


def slow_factor(segments: list[Segment], length: float) -> float:
    have = sum(s.length for s in segments)
    return min(1.25, max(1.0, length / have)) if have > 0 else 1.0     # un filo di rallentatore se serve


def timeline(segments: list[Segment], length: float) -> list[tuple[float, float]]:
    """Dove cade ogni tratto nel video finito (l'ultimo dura fino alla fine della parte girata)."""
    slow = slow_factor(segments, length)
    out, t = [], 0.0
    for s in segments:
        out.append((t, min(length, t + s.length * slow)))
        t += s.length * slow
    if out:
        out[-1] = (out[-1][0], length)
    return out


def build_footage(spec: ClipSpec, td: Path, length: float) -> Path:
    """Tratti tagliati, verticali, stabilizzati e uniti, lunghi `length` secondi (con audio)."""
    ffmpeg = ffmpeg_path()
    segs = spec.segments
    slow = slow_factor(segs, length)
    parts: list[str] = []
    stab = has_filter("vidstabdetect") and has_filter("vidstabtransform")
    for i, s in enumerate(segs):
        base = _crop_filter(spec.info) + f",fps={FPS},setpts={slow:.4f}*PTS"
        common = [ffmpeg, "-y", "-v", "error", "-ss", f"{s.start:.3f}", "-t", f"{s.length:.3f}", "-i", str(spec.source)]
        out = f"seg{i}.mp4"
        audio = ["-af", f"atempo={1 / slow:.4f},aresample=48000", "-c:a", "aac", "-b:a", "128k", "-ac", "2"] \
            if spec.info.has_audio else ["-an"]
        if stab:
            # Passo 1: misura il tremolio. Passo 2: lo compensa (zoom fisso del 5% per non vedere i bordi).
            _run(common + ["-vf", f"{base},vidstabdetect=shakiness=6:accuracy=12:result=t{i}.trf", "-an",
                           "-f", "null", "-"], td, "Stabilizzazione (misura)")
            vf = f"{base},vidstabtransform=input=t{i}.trf:smoothing=18:zoom=5:optzoom=0:interpol=bicubic," \
                 f"unsharp=5:5:0.5:3:3:0"
        elif has_filter("deshake"):
            vf = f"{base},deshake,scale={int(W * 1.05) // 2 * 2}:{int(H * 1.05) // 2 * 2},crop={W}:{H}"
        else:
            vf = base
        _run(common + ["-vf", vf, *audio, "-c:v", "libx264", "-preset", "veryfast", "-crf", "17",
                       "-pix_fmt", "yuv420p", out], td, "Montaggio del tratto")
        parts.append(out)
    n = len(parts)
    inputs: list[str] = []
    for p in parts:
        inputs += ["-i", p]
    if spec.info.has_audio:
        chain = "".join(f"[{k}:v][{k}:a]" for k in range(n)) + f"concat=n={n}:v=1:a=1[cv][ca]"
        maps = ["-map", "[v]", "-map", "[a]"]
        audio_tail = f";[ca]apad,atrim=0:{length:.3f}[a]"
    else:
        chain = "".join(f"[{k}:v]" for k in range(n)) + f"concat=n={n}:v=1:a=0[cv]"
        maps = ["-map", "[v]", "-map", f"{n}:a"]
        inputs += ["-f", "lavfi", "-t", f"{length:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
        audio_tail = ""
    # Se i tratti non bastano, l'ultimo fotogramma resta fermo fino alla fine della voce.
    graph = f"{chain};[cv]tpad=stop_mode=clone:stop_duration={length:.3f},trim=0:{length:.3f},setpts=PTS-STARTPTS[v]" \
            + audio_tail
    _run([ffmpeg, "-y", "-v", "error", *inputs, "-filter_complex", graph, *maps, "-c:v", "libx264",
          "-preset", "veryfast", "-crf", "17", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
          "-t", f"{length:.3f}", "footage.mp4"], td, "Unione dei tratti")
    return td / "footage.mp4"


# ------------------------------------------------------------------ grafica

def caption_chunks(text: str, max_chars: int = 30) -> list[str]:
    """Spezza un testo in sottotitoli brevi: prima per frasi, poi in pezzi di lunghezza simile,
    senza mai tagliare una parola né unire la fine di una frase con l'inizio della successiva."""
    import re
    sentences = [x.strip() for x in re.split(r"(?<=[.!?…])\s+", text.strip()) if x.strip()]
    out: list[str] = []
    for sent in sentences:
        words = sent.split()
        n = max(1, math.ceil(len(sent) / max_chars))
        chunks = [sent]
        while n <= len(words):
            target = len(sent) / n
            chunks, cur = [], ""
            for w in words:
                t = (cur + " " + w).strip()
                if cur and len(t) > target * 1.15 and len(chunks) < n - 1:
                    chunks.append(cur)
                    cur = w
                else:
                    cur = t
                    # pausa naturale (virgola, due punti) abbastanza avanti: si va a capo lì
                    if cur.endswith((",", ":", ";")) and len(cur) >= target * 0.6 and len(chunks) < n - 1:
                        chunks.append(cur)
                        cur = ""
            if cur:
                chunks.append(cur)
            if all(len(c) <= max_chars + 4 for c in chunks):
                break
            n += 1
        out.extend(chunks)
    return out


def caption_timing(chunks: list[str], start: float, end: float) -> list[tuple[str, float, float]]:
    """Tempi dei sottotitoli in proporzione alla lunghezza di ogni pezzo (la voce dura quanto il testo)."""
    if not chunks or end <= start:
        return []
    weights = [max(6, len(c)) for c in chunks]
    total = sum(weights)
    out, t = [], start
    for c, wgt in zip(chunks, weights):
        d = (end - start) * wgt / total
        out.append((c, t, t + d))
        t += d
    return out


def _gradient(height: int, top: bool, max_alpha: int) -> Image.Image:
    a = np.linspace(1, 0, height) if top else np.linspace(0, 1, height)
    a = (a ** 1.6 * max_alpha).astype(np.uint8)
    img = np.zeros((height, W, 4), dtype=np.uint8)
    img[..., 3] = a[:, None]
    return Image.fromarray(img, "RGBA")


_NBSP = "\u00a0"


def _glue(text: str) -> str:
    """Spazi che non si spezzano: "700 g", "€ 3,99", "al kg" restano sulla stessa riga."""
    import re
    text = re.sub(r"(\d)\s+(g|kg|l|ml|cl|pz|%)\b", lambda m: m.group(1) + _NBSP + m.group(2), text)
    text = re.sub(r"€\s+(\d)", lambda m: "€" + _NBSP + m.group(1), text)
    return re.sub(r"\b(al|a|da|di|e|il|la|le|lo)\s+", lambda m: m.group(1) + _NBSP, text)


def _balanced(text: str, f, max_w: int) -> list[str]:
    """Due righe di lunghezza simile invece di una lunga e una con una parola sola."""
    words = text.split(" ")
    if len(words) < 2 or f.getlength(text) <= max_w:
        return [text]
    best = None
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        wa, wb = f.getlength(a), f.getlength(b)
        if max(wa, wb) <= max_w and (best is None or max(wa, wb) < best[0]):
            best = (max(wa, wb), [a, b])
    return best[1] if best else []


def _outlined(text: str, size: int, color=(255, 255, 255), stroke: int = 0, max_w: int = W - 120,
              lines: int = 2, align: str = "center") -> Image.Image:
    text = _glue(text)
    f, ln = fit_text(text, max_w, int(size * 1.25 * lines), size, True, lines, min_size=int(size * 0.6))
    if lines == 2:
        size_try = size
        while size_try >= int(size * 0.6):
            fb = font(size_try, True)
            bal = _balanced(text, fb, max_w)
            if bal:
                f, ln = fb, bal
                break
            size_try = int(size_try * 0.92)
    ln = [x.replace(_NBSP, " ") for x in ln]
    lh = int(f.size * 1.18)
    width = max((int(f.getlength(x)) for x in ln), default=1) + 2 * stroke + 8
    img = Image.new("RGBA", (width, lh * len(ln) + 2 * stroke + int(f.size * 0.3)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i, line in enumerate(ln):
        lw = f.getlength(line)
        x = stroke + 4 + ((width - 2 * stroke - 8 - lw) / 2 if align == "center" else 0)
        d.text((x, stroke + i * lh), line, font=f, fill=color + (255,), stroke_width=stroke,
               stroke_fill=(0, 0, 0, 230))
    return img


class ClipOverlay:
    """Disegna la grafica sopra il video, fotogramma per fotogramma (sfondo trasparente)."""

    def __init__(self, spec: ClipSpec, footage: float, voice_start: float, voice_len: float):
        self.spec, self.F = spec, footage
        t = spec.text
        self.brand = hex_rgb(spec.brand_color)
        self.accent = hex_rgb(spec.accent_color)
        self.top = _gradient(420, True, 165)
        self.bottom = _gradient(900, False, 215)
        # intestazione: logo e nome
        self.logo = logo_image(spec.logo_path, 300, 120, (30, 30, 30))
        self.name = _outlined(spec.store_name, 48, stroke=3, max_w=W - 120 - (self.logo.width + 24 if self.logo else 0),
                              lines=1, align="left")
        self.ai_label = pill("Voce generata con IA", 24, (20, 20, 20)) if spec.voice_is_ai else None
        # titolo d'apertura in un riquadro del colore del negozio
        self.hook = None
        if t.hook:
            f, ln = fit_text(t.hook, W - 220, 230, 76, True, 2, min_size=44)
            lh = int(f.size * 1.16)
            tw = max(int(f.getlength(x)) for x in ln)
            box = Image.new("RGBA", (tw + 80, lh * len(ln) + 56), (0, 0, 0, 0))
            d = ImageDraw.Draw(box)
            d.rounded_rectangle((0, 0, box.width - 1, box.height - 1), radius=30, fill=self.brand + (245,))
            for i, line in enumerate(ln):
                d.text((box.width / 2, 28 + i * lh), line, font=f, fill=text_on(self.brand) + (255,), anchor="ma")
            self.hook = box
        # cartellini prodotto: uno per tratto, ognuno nel suo intervallo di tempo
        self.until = None
        if t.validity:
            until = ("Fino al " + t.validity.rsplit(" al ", 1)[-1]) if " al " in t.validity else t.validity
            self.until = pill(until[:1].upper() + until[1:], 30, self.accent)
        spans = timeline(spec.segments, footage)
        self.cards = []
        for k, (a, b) in enumerate(spans):
            card = t.cards[k] if k < len(t.cards) else None
            if card is None:
                continue
            # tratti consecutivi con lo stesso prodotto: un solo cartellino, senza riapparire
            if self.cards and self.cards[-1][0] is card:
                self.cards[-1] = (card, self.cards[-1][1], b, self.cards[-1][3])
                continue
            self.cards.append((card, max(a, 0.9 if k == 0 else a), b, self._card_layers(card)))
        # sottotitoli: con la voce seguono il parlato, senza voce scorrono dopo il titolo
        start = voice_start if voice_len > 0 else (3.4 if self.hook else 0.8)
        end = voice_start + voice_len if voice_len > 0 else footage - 0.4
        self.caps = [(_outlined(c, 60, stroke=5, lines=2), a, b)
                     for c, a, b in caption_timing(t.captions, start, max(start + 1.0, min(end, footage - 0.2)))]
        if not t.captions and t.segment_lines:
            hook_end = (min(3.2, footage * 0.45) + 0.35) if self.hook is not None else 0.4
            for line, (a, b) in zip(t.segment_lines, timeline(spec.segments, footage)):
                a = max(a + 0.3, hook_end)
                if line and b - a >= 1.0:
                    self.caps.append((_outlined(line, 60, stroke=5, lines=2), a, b - 0.15))
        self.outro = Renderer(spec.outro)._outro() if spec.outro is not None else None

    def _card_layers(self, card: ProductCard) -> list[tuple[Image.Image, str]]:
        """Livelli dal basso verso l'alto: validità, dettagli, prezzo, formato, nome, marca."""
        out: list[tuple[Image.Image, str]] = []
        if self.until is not None:
            out.append((self.until, "valid"))
        extra = " · ".join(x for x in (card.unit_text, card.conditions) if x)
        if extra:
            out.append((_outlined(extra, 32, stroke=2, lines=1, align="left"), "extra"))
        out.append((price_block(card.price_cents, 196, self.brand), "price"))
        if card.description:
            out.append((_outlined(card.description, 36, stroke=2, max_w=W - 140, lines=1, align="left"), "desc"))
        out.append((_outlined(card.product, 70, stroke=4, max_w=W - 140, lines=2, align="left"), "name"))
        if card.brand and card.brand.lower() not in card.product.lower():
            out.append((_outlined(card.brand.upper(), 30, color=self.accent, stroke=2, lines=1, align="left"), "brand"))
        return out

    def frame(self, t: float) -> Image.Image:
        if t >= self.F and self.outro is not None:
            p = (t - self.F) / OUTRO_SECONDS
            return self.outro(min(1.0, p)).convert("RGBA")
        c = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        fade_out = 1 - ease_in((t - (self.F - 0.35)) / 0.35) if t > self.F - 0.35 else 1.0
        c.alpha_composite(self.top, (0, 0))
        c.alpha_composite(self.bottom, (0, H - self.bottom.height))
        # intestazione
        x = 54
        if self.logo is not None:
            paste(c, self.logo, x, 70, 1.0)
            x += self.logo.width + 24
            ny = 70 + (self.logo.height - self.name.height) / 2
        else:
            ny = 80
        paste(c, self.name, x, ny, 1.0)
        if self.ai_label is not None:
            paste(c, self.ai_label, W - self.ai_label.width - 40, 220, 0.9)
        # titolo
        if self.hook is not None:
            end = min(3.2, self.F * 0.45)
            if t < end + 0.4:
                q = ease_out((t - 0.25) / 0.35)
                out = ease_in((t - end) / 0.35) if t > end else 0
                if q > 0:
                    paste(c, self.hook, (W - self.hook.width) / 2, 520 + (1 - q) * 60 - out * 40, q * (1 - out))
        # sottotitoli
        for img, a, b in self.caps:
            if a - 0.05 <= t <= b + 0.05:
                q = ease_out((t - a) / 0.12)
                paste(c, img, (W - img.width) / 2, 1060 - img.height / 2, min(1.0, q))
                break
        # cartellino del prodotto inquadrato: entra, il prezzo fa "pop", esce al cambio di prodotto
        for card, a, b, blocks in self.cards:
            if not (a <= t <= b + 0.3):
                continue
            leave = ease_in((t - (b - 0.25)) / 0.25) if t > b - 0.25 and b < self.F - 0.5 else 0.0
            alpha_out = (1 - leave) * fade_out
            y = H - 120
            for k, (img, kind) in enumerate(blocks):
                y -= img.height + (18 if kind != "price" else 22)
                if kind == "price":
                    q = ease_back((t - a - 0.45) / 0.3)
                    if q > 0:
                        lay = scaled(img, max(0.05, q))
                        paste(c, lay, 64 + (img.width - lay.width) / 2 - leave * 120,
                              y + (img.height - lay.height) / 2, alpha_out)
                else:
                    q = ease_out((t - a - 0.06 * (len(blocks) - k)) / 0.35)
                    if q > 0:
                        paste(c, img, 64 - (1 - q) * 80 - leave * 120, y, q * alpha_out)
        return c


# ------------------------------------------------------------------ montaggio finale

def plan_length(segments: list[Segment], voice_len: float) -> float:
    """Durata della parte girata: quanto basta per la voce, entro limiti da Reel."""
    have = sum(s.length for s in segments)
    want = voice_len + 1.2 if voice_len > 0 else min(max(have, MIN_FOOTAGE), 14.0)
    return float(min(MAX_FOOTAGE, max(MIN_FOOTAGE, want)))


def render_clip(spec: ClipSpec, out_path: Path) -> tuple[Path, float]:
    """Crea il Reel. Restituisce il percorso e la durata in secondi."""
    if not spec.segments:
        raise RenderError("Nessun tratto utilizzabile nel video.")
    ffmpeg = ffmpeg_path()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        td = Path(tmp)
        voice_len = 0.0
        voice_wav = None
        if spec.voice_path is not None:
            voice_wav = td / "voce.wav"
            voice_len = clean_voice(spec.voice_path, voice_wav)
            if voice_len > MAX_FOOTAGE - 1.5:
                raise RenderError(f"La voce dura {voice_len:.0f} secondi: per un Reel ne bastano al massimo "
                                  f"{MAX_FOOTAGE - 2:.0f}.")
        footage_len = plan_length(spec.segments, voice_len)
        footage = build_footage(spec, td, footage_len)
        outro = OUTRO_SECONDS if spec.outro is not None else 0.0
        total = footage_len + outro
        voice_start = 0.5
        overlay = ClipOverlay(spec, footage_len, voice_start, voice_len)

        inputs = ["-i", footage.name, "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-"]
        mix, labels = [], []
        n_in = 2
        amb_vol = 0.18 if voice_wav else 0.35
        mix.append(f"[0:a]volume={amb_vol if spec.ambient else 0},afade=t=out:st={max(0.0, footage_len - 0.6):.2f}:d=0.6,"
                   f"apad,atrim=0:{total:.3f}[amb]")
        labels.append("[amb]")
        if spec.music:
            transitions, t = [], 0.0
            for s in spec.segments[:-1]:
                t += s.length
                transitions.append(t)
            music = compose(total, transitions + [footage_len], [1.5])
            write_wav(music, td / "musica.wav")
            inputs += ["-i", "musica.wav"]
            mvol = 0.28 if voice_wav else 0.7
            mix.append(f"[{n_in}:a]aresample=48000,volume={mvol}[mus]")
            labels.append("[mus]")
            n_in += 1
        if voice_wav is not None:
            inputs += ["-i", voice_wav.name]
            ms = int(voice_start * 1000)
            mix.append(f"[{n_in}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={ms}|{ms}[voc]")
            labels.append("[voc]")
            n_in += 1
        graph = (f"[0:v]tpad=stop_mode=add:stop_duration={outro:.3f}:color=black[base];"
                 f"[base][1:v]overlay=0:0:format=auto,format=yuv420p[v];" + ";".join(mix) + ";" +
                 "".join(labels) + f"amix=inputs={len(labels)}:normalize=0:duration=longest,"
                 f"alimiter=limit=0.95,atrim=0:{total:.3f}[a]")
        tmp_out = td / "reel.mp4"
        cmd = [ffmpeg, "-y", "-v", "error", *inputs, "-filter_complex", graph, "-map", "[v]", "-map", "[a]",
               "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "aac", "-b:a", "160k",
               "-t", f"{total:.3f}", "-movflags", "+faststart", tmp_out.name]
        proc = subprocess.Popen(cmd, cwd=str(td), stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            assert proc.stdin is not None
            for i in range(int(math.ceil(total * FPS))):
                proc.stdin.write(overlay.frame(i / FPS).tobytes())
            proc.stdin.close()
            err = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
            code = proc.wait()
        except BrokenPipeError:
            err = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
            proc.wait()
            raise RenderError(f"Il montaggio si è interrotto: {err.strip()[-500:]}")
        except BaseException:
            proc.kill()
            proc.wait()
            raise
        if code != 0:
            raise RenderError(f"Il montaggio non è riuscito: {err.strip()[-500:]}")
        shutil.move(str(tmp_out), str(out_path))
    return out_path, total


def poster(path: Path, t: float, out: Path) -> Path | None:
    try:
        proc = subprocess.run([ffmpeg_path(), "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", str(path),
                               "-frames:v", "1", "-q:v", "3", str(out)], capture_output=True)
        return out if proc.returncode == 0 and out.exists() else None
    except OSError:
        return None


__all__ = ["ClipSpec", "ClipText", "ProductCard", "timeline", "render_clip", "caption_chunks", "caption_timing", "plan_length", "poster",
           "clean_voice", "has_filter", "SR"]
