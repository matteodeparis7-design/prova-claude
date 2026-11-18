"""Guarda un video girato col telefono e sceglie i momenti migliori.

Per ogni fotogramma (5 al secondo, in piccolo) misura:
- nitidezza: varianza del laplaciano, bassa se il video è mosso o sfocato;
- colore: i banchi del fresco sono colorati, pavimento e soffitto no;
- luce: scarta i tratti troppo bui o bruciati;
- movimento: differenza con il fotogramma prima, alta quando il telefono viene spostato di colpo.
Poi sceglie fino a 3 tratti di 2,5-5 secondi con il punteggio più alto, senza tagliare a metà
un cambio d'inquadratura, e li rimette in ordine di tempo.
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from ..video.render import RenderError, ffmpeg_path

SAMPLE_FPS = 5
SAMPLE_W = 160


class ClipError(RenderError):
    """Video non utilizzabile (formato, durata, contenuto)."""


@dataclass
class VideoInfo:
    width: int            # dimensioni come si vedono (rotazione del telefono già applicata)
    height: int
    duration: float
    fps: float
    rotation: int
    has_audio: bool

    @property
    def vertical(self) -> bool:
        return self.height > self.width


@dataclass
class Segment:
    start: float
    end: float
    score: float
    best_time: float      # il fotogramma più bello del tratto (per riconoscere il prodotto)

    @property
    def length(self) -> float:
        return self.end - self.start


@dataclass
class Analysis:
    info: VideoInfo
    times: np.ndarray
    score: np.ndarray
    cuts: list[float] = field(default_factory=list)
    segments: list[Segment] = field(default_factory=list)

    @property
    def usable_seconds(self) -> float:
        return sum(s.length for s in self.segments)


def probe(path: Path) -> VideoInfo:
    """Legge dimensioni, durata, rotazione e audio con ffmpeg (ffprobe non serve)."""
    proc = subprocess.run([ffmpeg_path(), "-hide_banner", "-i", str(path)], capture_output=True, text=True)
    err = proc.stderr
    vline = next((ln for ln in err.splitlines() if "Video:" in ln), "")
    if not vline:
        raise ClipError("Il file non contiene un video leggibile.")
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", err)
    duration = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0
    size = re.search(r",\s*(\d{2,5})x(\d{2,5})", vline)
    if not size:
        raise ClipError("Dimensioni del video non riconosciute.")
    w, h = int(size.group(1)), int(size.group(2))
    fps_m = re.search(r"(\d+(?:\.\d+)?)\s*fps", vline)
    fps = float(fps_m.group(1)) if fps_m else 30.0
    rot = 0
    rm = re.search(r"rotation of (-?\d+(?:\.\d+)?) degrees", err) or re.search(r"rotate\s*:\s*(-?\d+)", err)
    if rm:
        rot = int(round(float(rm.group(1)))) % 360
    if rot in (90, 270):                    # ffmpeg ruota da solo in lettura: contano le dimensioni ruotate
        w, h = h, w
    has_audio = any("Audio:" in ln for ln in err.splitlines())
    if duration <= 0:
        raise ClipError("Durata del video non riconosciuta.")
    return VideoInfo(w, h, duration, fps, rot, has_audio)


def _frames(path: Path, info: VideoInfo) -> tuple[np.ndarray, np.ndarray]:
    sw = SAMPLE_W
    sh = max(2, int(round(sw * info.height / info.width / 2)) * 2)
    cmd = [ffmpeg_path(), "-v", "error", "-i", str(path), "-vf", f"fps={SAMPLE_FPS},scale={sw}:{sh}",
           "-pix_fmt", "rgb24", "-f", "rawvideo", "-"]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0 and not proc.stdout:
        raise ClipError("Non riesco a leggere i fotogrammi del video: " + proc.stderr.decode(errors="replace")[:300])
    frame_size = sw * sh * 3
    n = len(proc.stdout) // frame_size
    if n == 0:
        raise ClipError("Il video non contiene fotogrammi.")
    arr = np.frombuffer(proc.stdout[: n * frame_size], dtype=np.uint8).reshape(n, sh, sw, 3)
    times = (np.arange(n) + 0.5) / SAMPLE_FPS
    return arr, times


def frame_metrics(rgb: np.ndarray) -> dict[str, np.ndarray]:
    """Metriche per fotogramma (array N x H x W x 3, uint8)."""
    f = rgb.astype(np.float32)
    gray = f @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    lap = (gray[:, 1:-1, 2:] + gray[:, 1:-1, :-2] + gray[:, 2:, 1:-1] + gray[:, :-2, 1:-1]
           - 4 * gray[:, 1:-1, 1:-1])
    sharp = lap.reshape(len(f), -1).var(axis=1)
    r, g, b = f[..., 0], f[..., 1], f[..., 2]
    rg, yb = r - g, 0.5 * (r + g) - b
    colorful = (np.sqrt(rg.reshape(len(f), -1).std(axis=1) ** 2 + yb.reshape(len(f), -1).std(axis=1) ** 2)
                + 0.3 * np.sqrt(rg.reshape(len(f), -1).mean(axis=1) ** 2 + yb.reshape(len(f), -1).mean(axis=1) ** 2))
    bright = gray.reshape(len(f), -1).mean(axis=1)
    motion = np.zeros(len(f), dtype=np.float32)
    if len(f) > 1:
        motion[1:] = np.abs(np.diff(gray, axis=0)).reshape(len(f) - 1, -1).mean(axis=1)
        motion[0] = motion[1]
    # cambio d'inquadratura: istogrammi del colore molto diversi tra un fotogramma e il successivo
    hist = np.stack([np.histogram(x, bins=16, range=(0, 255))[0] for x in gray]).astype(np.float32)
    hist /= hist.sum(axis=1, keepdims=True) + 1e-6
    change = np.zeros(len(f), dtype=np.float32)
    if len(f) > 1:
        change[1:] = 0.5 * np.abs(np.diff(hist, axis=0)).sum(axis=1)
    return {"sharp": sharp, "colorful": colorful, "bright": bright, "motion": motion, "change": change}


def _z(x: np.ndarray) -> np.ndarray:
    sd = x.std()
    return (x - np.median(x)) / (sd if sd > 1e-6 else 1.0)


def frame_scores(m: dict[str, np.ndarray]) -> np.ndarray:
    sharp = np.log1p(m["sharp"])
    s = 1.0 * _z(sharp) + 0.6 * _z(m["colorful"]) - 0.8 * _z(np.log1p(m["motion"]))
    s = s - np.where(m["bright"] < 45, (45 - m["bright"]) / 8, 0)          # troppo buio
    s = s - np.where(m["bright"] > 235, (m["bright"] - 235) / 4, 0)        # bruciato
    # Assoluto: un fotogramma molto mosso non è mai "buono", anche se tutto il video è mosso.
    s = s - np.where(sharp < np.log1p(8.0), 2.0, 0)
    return s.astype(np.float32)


def scene_cuts(m: dict[str, np.ndarray], times: np.ndarray) -> list[float]:
    """Cambi d'inquadratura: salto netto dei colori rispetto al resto del video (soglia relativa)."""
    ch = m["change"]
    threshold = max(0.12, 8 * float(np.median(ch)))
    return [float(t) for t, c in zip(times, ch) if c > threshold]


def pick_segments(times: np.ndarray, score: np.ndarray, cuts: list[float], target: float,
                  min_len: float = 2.5, max_len: float = 5.0, max_segments: int = 3) -> list[Segment]:
    """Sceglie i tratti migliori fino a coprire `target` secondi (se il video lo permette)."""
    if len(times) == 0:
        return []
    dur = float(times[-1] + 0.5 / SAMPLE_FPS)
    step = 1 / SAMPLE_FPS
    if dur <= min_len + 0.4:                             # video cortissimo: si usa tutto, tranne i bordi
        a, b = min(0.15, dur * 0.05), max(dur - 0.15, dur * 0.95)
        return [Segment(a, b, float(score.mean()), float(times[int(np.argmax(score))]))]
    smooth = np.convolve(score, np.ones(3) / 3, mode="same")
    chosen: list[Segment] = []
    used = np.zeros(len(times), dtype=bool)
    floor_ = float(np.percentile(smooth, 35))
    while len(chosen) < max_segments and sum(s.length for s in chosen) < target - 0.5:
        remaining = target - sum(s.length for s in chosen)
        best = None
        for length in (max_len, 4.0, 3.2, min_len):
            length = min(length, max(min_len, remaining))
            n = max(1, int(round(length / step)))
            for i in range(0, len(times) - n + 1):
                if used[i:i + n].any():
                    continue
                a, b = float(times[i] - step / 2), float(times[i + n - 1] + step / 2)
                if any(a + 0.2 < c < b - 0.2 for c in cuts):       # non attraversare un cambio d'inquadratura
                    continue
                window = smooth[i:i + n]
                val = float(window.mean()) - 0.6 * float(window.std())   # costante, non a sbalzi
                if best is None or val > best[0] + 1e-6:
                    best = (val, i, n)
            if best is not None and best[0] >= floor_:
                break
        if best is None or (chosen and best[0] < floor_):
            break
        _, i, n = best
        seg_scores = score[i:i + n]
        chosen.append(Segment(float(max(0.0, times[i] - step / 2)), float(min(dur, times[i + n - 1] + step / 2)),
                              float(seg_scores.mean()), float(times[i + int(np.argmax(seg_scores))])))
        lo, hi = max(0, i - int(0.6 / step)), min(len(times), i + n + int(0.6 / step))
        used[lo:hi] = True                                 # un po' di margine tra un tratto e l'altro
    if not chosen:                                         # tutto scadente: il tratto meno peggio
        n = min(len(times), int(round(min(max_len, dur) / step)))
        i = int(np.argmax(np.convolve(smooth, np.ones(n) / n, mode="valid")))
        chosen = [Segment(float(times[i] - step / 2), float(times[i + n - 1] + step / 2),
                          float(score[i:i + n].mean()), float(times[i + int(np.argmax(score[i:i + n]))]))]
    # Un tratto che parte (o finisce) a ridosso di un cambio d'inquadratura viene allineato al cambio:
    # niente "mezzo secondo" del prodotto precedente in apertura.
    for seg in chosen:
        for c in cuts:
            if seg.start - 0.01 <= c <= seg.start + 0.45 and seg.end - (c + 0.1) >= 1.5:
                seg.start = c + 0.1
            if seg.end - 0.45 <= c <= seg.end + 0.01 and (c - 0.1) - seg.start >= 1.5:
                seg.end = c - 0.1
        seg.best_time = min(max(seg.best_time, seg.start), seg.end)
    return sorted(chosen, key=lambda s: s.start)


def scenes(times: np.ndarray, cuts: list[float]) -> list[tuple[int, int]]:
    """Inquadrature continue, come intervalli di indici [i, j) dei fotogrammi campionati."""
    bounds = [0] + [int(np.searchsorted(times, c)) for c in cuts] + [len(times)]
    return [(a, b) for a, b in zip(bounds, bounds[1:]) if b > a]


def pick_in_main_scene(times: np.ndarray, score: np.ndarray, cuts: list[float], target: float,
                       max_segments: int = 3) -> tuple[list[Segment], bool]:
    """Come pick_segments, ma solo dentro l'inquadratura principale (la più lunga tra quelle buone).

    Serve quando il prodotto lo indica il negoziante: se il video passa da un prodotto all'altro,
    il cartellino non deve finire sopra il prodotto sbagliato. Restituisce anche se ha scartato qualcosa."""
    parts = scenes(times, cuts)
    if len(parts) <= 1:
        return pick_segments(times, score, cuts, target, max_segments=max_segments), False
    def value(ab):
        a, b = ab
        good = score[a:b]
        return float(np.clip(good - np.percentile(score, 30), 0, None).sum())
    a, b = max(parts, key=value)
    # i tempi del sotto-intervallo sono già quelli del video intero
    segs = pick_segments(times[a:b], score[a:b], [], target, max_segments=max_segments)
    lo, hi = float(times[a] - 0.5 / SAMPLE_FPS), float(times[b - 1] + 0.5 / SAMPLE_FPS)
    for seg in segs:
        seg.start, seg.end = max(seg.start, lo), min(seg.end, hi)
    return [x for x in segs if x.length > 0.5], True


def analyze(path: Path, target: float = 11.0) -> Analysis:
    info = probe(path)
    if info.duration < 1.5:
        raise ClipError("Il video è troppo corto: servono almeno 2 secondi.")
    if info.duration > 180:
        raise ClipError("Il video è troppo lungo: massimo 3 minuti.")
    rgb, times = _frames(path, info)
    m = frame_metrics(rgb)
    score = frame_scores(m)
    cuts = scene_cuts(m, times)
    segs = pick_segments(times, score, cuts, target)
    return Analysis(info=info, times=times, score=score, cuts=cuts, segments=segs)


def grab_frame(path: Path, t: float, width: int = 768) -> bytes:
    """Un fotogramma in JPEG (per far riconoscere il prodotto all'IA e per l'anteprima)."""
    proc = subprocess.run([ffmpeg_path(), "-v", "error", "-ss", f"{max(0.0, t):.2f}", "-i", str(path),
                           "-frames:v", "1", "-vf", f"scale={width}:-2", "-q:v", "3", "-f", "image2", "-"],
                          capture_output=True)
    if proc.returncode != 0 or not proc.stdout:
        raise ClipError("Non riesco a estrarre un fotogramma dal video.")
    return proc.stdout
