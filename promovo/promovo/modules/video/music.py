"""Musica originale per i video, generata al momento (nessun diritto d'autore da pagare).

Brano pop leggero in La maggiore a 112 BPM: pad morbido, arpeggio pizzicato, basso, batteria
leggera. Gli effetti (whoosh sulle transizioni, "pop" sui prezzi) cadono sui tempi del video.
Solo numpy: i filtri sono fatti nel dominio delle frequenze, così funziona ovunque (anche su
Windows con versioni di Python nuovissime, senza pacchetti da compilare).
"""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SR = 44100
BPM = 112
BEAT = 60 / BPM
BAR = 4 * BEAT

# Accordi (basso, voci del pad, note dell'arpeggio) in note MIDI: A - E/G# - F#m - D
CHORDS = [
    (45, [57, 61, 64, 68, 71], [69, 73, 76, 80, 81, 76, 73, 76]),
    (40, [56, 59, 64, 66, 71], [68, 71, 76, 78, 80, 76, 71, 76]),
    (42, [57, 61, 64, 66, 69], [69, 73, 76, 78, 81, 78, 73, 76]),
    (38, [57, 62, 66, 69, 73], [66, 69, 74, 78, 81, 78, 74, 69]),
]


def mtof(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def fft_filter(x: np.ndarray, lo: float = 0.0, hi: float = SR / 2) -> np.ndarray:
    """Filtro passa-banda morbido (dominio delle frequenze)."""
    n = len(x)
    if n < 8:
        return x
    spec = np.fft.rfft(x, axis=0)
    f = np.fft.rfftfreq(n, 1 / SR)
    gain = np.ones_like(f)
    if lo > 0:
        gain *= 1 / np.sqrt(1 + (lo / np.maximum(f, 1e-3)) ** 4)
    if hi < SR / 2:
        gain *= 1 / np.sqrt(1 + (f / hi) ** 4)
    if spec.ndim == 2:
        gain = gain[:, None]
    return np.fft.irfft(spec * gain, n=n, axis=0).astype(np.float32)


def env(n: int, attack: float, decay: float, sustain: float = 0.0, release: float = 0.05) -> np.ndarray:
    t = np.arange(n) / SR
    a = np.clip(t / max(attack, 1e-4), 0, 1)
    d = sustain + (1 - sustain) * np.exp(-np.maximum(t - attack, 0) / max(decay, 1e-4))
    tail = np.clip((n / SR - t) / max(release, 1e-4), 0, 1)
    return (a * d * tail).astype(np.float32)


def saw(freq: float, n: int, detune: float = 0.0, phase: float = 0.0) -> np.ndarray:
    t = np.arange(n) / SR
    ph = (phase + freq * (1 + detune) * t) % 1.0
    return (2 * ph - 1).astype(np.float32)


class Mixer:
    def __init__(self, seconds: float, seed: int = 7):
        self.n = int(seconds * SR) + SR
        self.buf = np.zeros((self.n, 2), np.float32)
        self.rng = np.random.default_rng(seed)

    def add(self, t: float, x: np.ndarray, gain: float = 1.0, pan: float = 0.0) -> None:
        i = int(round(t * SR))
        if i >= self.n or i < 0:
            return
        if x.ndim == 1:
            left, right = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
            x = np.stack([x * left, x * right], 1) * 1.41
        k = min(len(x), self.n - i)
        self.buf[i:i + k] += x[:k] * gain


# ---------------------------------------------------------------- strumenti

def kick(rng) -> np.ndarray:
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    f = 48 + 90 * np.exp(-t * 32)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7.5)
    click = fft_filter(rng.standard_normal(n).astype(np.float32), 0, 3500) * np.exp(-t * 500) * 0.12
    return (body + click).astype(np.float32)


def clap(rng) -> np.ndarray:
    n = int(0.22 * SR)
    t = np.arange(n) / SR
    noise = rng.standard_normal(n).astype(np.float32)
    bursts = sum(np.exp(-np.maximum(t - d, 0) * 60) * (t >= d) for d in (0, 0.011, 0.022))
    x = fft_filter(noise * (bursts + np.exp(-t * 14) * 0.6), 900, 6000)
    return (x / (np.abs(x).max() + 1e-6)).astype(np.float32)


def hat(rng, open_: bool = False) -> np.ndarray:
    n = int((0.18 if open_ else 0.05) * SR)
    t = np.arange(n) / SR
    x = fft_filter(rng.standard_normal(n).astype(np.float32), 7000) * np.exp(-t * (14 if open_ else 70))
    return (x / (np.abs(x).max() + 1e-6)).astype(np.float32)


def pluck(m: float, dur: float = 0.45) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = mtof(m)
    x = (np.sin(2 * np.pi * f * t) + 0.45 * np.sin(4 * np.pi * f * t) * np.exp(-t * 9)
         + 0.2 * np.sin(6 * np.pi * f * t) * np.exp(-t * 16))
    return (x * env(n, 0.003, 0.22, 0.0, 0.05)).astype(np.float32)


def pad(notes: list[int], dur: float) -> np.ndarray:
    n = int(dur * SR)
    x = np.zeros(n, np.float32)
    for m in notes:
        for det in (-0.004, 0.0, 0.004):
            x += saw(mtof(m), n, det, phase=np.random.default_rng(m).random())
    x = fft_filter(x, 120, 1800) / (len(notes) * 3)
    return (x * env(n, 0.35, 99, 1.0, 0.5)).astype(np.float32)


def bass(m: float, dur: float) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = mtof(m)
    x = np.sin(2 * np.pi * f * t) + 0.3 * fft_filter(saw(f, n), 0, 500)
    return (x * env(n, 0.01, 0.5, 0.55, 0.06)).astype(np.float32)


def whoosh(rng, dur: float = 0.7) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    noise = rng.standard_normal(n).astype(np.float32)
    # Il rumore filtrato sale e scende: si fa con tre bande sfumate nel tempo.
    low = fft_filter(noise, 300, 1500)
    mid = fft_filter(noise, 1500, 4500)
    high = fft_filter(noise, 4500, 11000)
    p = t / dur
    shape = np.sin(np.pi * np.clip(p, 0, 1)) ** 1.5
    x = (low * (1 - p) + mid * np.sin(np.pi * p) + high * p) * shape
    return (x / (np.abs(x).max() + 1e-6)).astype(np.float32)


def pop() -> np.ndarray:
    n = int(0.12 * SR)
    t = np.arange(n) / SR
    f = 600 + 900 * np.exp(-t * 40)
    return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 30)).astype(np.float32)


def chime(m: float = 81) -> np.ndarray:
    n = int(1.6 * SR)
    t = np.arange(n) / SR
    f = mtof(m)
    x = sum(a * np.sin(2 * np.pi * f * k * t) * np.exp(-t * (2.5 + k)) for k, a in ((1, 1), (2.76, .4), (5.4, .2)))
    return (x * env(n, 0.002, 99, 1.0, 0.3)).astype(np.float32)


# ---------------------------------------------------------------- brano

def compose(seconds: float, transitions: list[float] = (), pops: list[float] = (), seed: int = 7) -> np.ndarray:
    """Brano stereo float32 lungo esattamente `seconds`, con effetti sui tempi indicati."""
    mx = Mixer(seconds, seed)
    rng = mx.rng
    k, cl, hc, ho = kick(rng), clap(rng), hat(rng), hat(rng, True)
    bars = int(np.ceil(seconds / BAR)) + 1
    end = seconds
    for b in range(bars):
        t0 = b * BAR
        if t0 >= end:
            break
        root, voices, arp = CHORDS[b % 4]
        mx.add(t0, pad(voices, BAR + 0.3), 0.20)
        intro = b == 0
        for i in range(8):                      # arpeggio a crome
            tt = t0 + i * BEAT / 2
            if tt < end:
                mx.add(tt, pluck(arp[i]), 0.11 if intro else 0.14, pan=(-0.35 if i % 2 else 0.35))
        if intro:
            continue
        for beat in range(4):
            tb = t0 + beat * BEAT
            if tb >= end:
                break
            mx.add(tb, k, 0.55)
            if beat in (1, 3):
                mx.add(tb, cl, 0.16, pan=0.05)
            mx.add(tb + BEAT / 2, ho if beat == 3 else hc, 0.07 if beat == 3 else 0.05, pan=0.25)
            mx.add(tb + BEAT / 4, hc, 0.03, pan=-0.25)
            mx.add(tb + 3 * BEAT / 4, hc, 0.03, pan=-0.25)
            mx.add(tb, bass(root, BEAT * 0.9), 0.30)
            mx.add(tb + BEAT * 0.75, bass(root + 12 if beat == 3 else root, BEAT * 0.25), 0.18)
    for t in transitions:
        if 0 < t < end:
            mx.add(max(0.0, t - 0.35), whoosh(rng), 0.13)
    for t in pops:
        if 0 < t < end:
            mx.add(t, pop(), 0.10, pan=0.1)
    mx.add(max(0.0, end - 2.2), chime(81), 0.12)
    mx.add(max(0.0, end - 2.2), chime(88), 0.08, pan=0.3)

    out = mx.buf[: int(seconds * SR)]
    # Eco leggera per dare spazio (ritardo di una croma, due ripetizioni).
    d = int(BEAT / 2 * SR)
    wet = np.zeros_like(out)
    for i, g in ((1, 0.22), (2, 0.1)):
        wet[d * i:] += out[:-d * i] * g if len(out) > d * i else 0
    wet[:, 0], wet[:, 1] = fft_filter(wet[:, 0], 200, 5000), fft_filter(wet[:, 1], 200, 5000)
    out = out + wet[:, ::-1]
    # Dissolvenze di inizio e fine, normalizzazione con margine.
    n = len(out)
    fade_in, fade_out = int(0.25 * SR), int(min(1.6, seconds / 4) * SR)
    ramp = np.ones(n, np.float32)
    ramp[:fade_in] = np.linspace(0, 1, fade_in)
    ramp[n - fade_out:] *= np.linspace(1, 0, fade_out) ** 1.5
    out *= ramp[:, None]
    peak = np.abs(out).max()
    if peak > 0:
        out *= 0.89 / peak
    return out.astype(np.float32)


def write_wav(samples: np.ndarray, path: Path) -> Path:
    pcm = (np.clip(samples, -1, 1) * 32767).astype("<i2")
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return path
