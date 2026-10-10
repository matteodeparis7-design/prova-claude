#!/usr/bin/env python3
"""Original 120 BPM track for the Superfreddo flyer video (synthesised, royalty free)."""
import sys, math, os
import numpy as np
from scipy import signal
sys.argv = ['x']
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_final as RF
R = RF.R

SR = 48000
BPM = 120; BEAT = 60 / BPM; BAR = 4 * BEAT; S16 = BEAT / 4
TOTAL = RF.TOTAL
N = int(TOTAL * SR) + SR * 4
rng = np.random.default_rng(3)

def buf(): return np.zeros((N, 2), np.float32)
def mtof(m): return 440 * 2 ** ((m - 69) / 12)
def add(b, t, x, gain=1.0, pan=0.0):
    i = int(round(t * SR))
    if i >= N: return
    if x.ndim == 1:
        l = math.cos((pan + 1) * math.pi / 4); r = math.sin((pan + 1) * math.pi / 4)
        x = np.stack([x * l * 1.414, x * r * 1.414], 1)
    n = min(len(x), N - i)
    b[i:i + n] += x[:n] * gain

def env_adsr(n, a, d, s, r, hold):
    t = np.arange(n) / SR
    e = np.where(t < a, t / max(a, 1e-4), s + (1 - s) * np.exp(-(t - a) / max(d, 1e-4)))
    rel = np.clip((t - hold) / max(r, 1e-4), 0, 1)
    return (e * (1 - rel) ** 2).astype(np.float32)

def polyblep_saw(freq, n, phase0=0.0):
    t = np.arange(n)
    dt = freq / SR
    ph = (phase0 + dt * t) % 1.0
    y = 2 * ph - 1
    m1 = ph < dt; x = ph[m1] / dt; y[m1] -= x + x - x * x - 1
    m2 = ph > 1 - dt; x = (ph[m2] - 1) / dt; y[m2] -= x * x + x + x + 1
    return y.astype(np.float32)

def lp(x, fc, q=0.707):
    b, a = signal.butter(2, min(fc, SR * 0.45) / (SR / 2), 'low')
    return signal.lfilter(b, a, x, axis=0).astype(np.float32)
def hp(x, fc):
    b, a = signal.butter(2, fc / (SR / 2), 'high')
    return signal.lfilter(b, a, x, axis=0).astype(np.float32)
def bp(x, f1, f2):
    b, a = signal.butter(2, [f1 / (SR / 2), f2 / (SR / 2)], 'band')
    return signal.lfilter(b, a, x, axis=0).astype(np.float32)

# ------------------------------------------------------------------ harmony (A major)
# bar -> (bass midi, pad voicing, arp tones)
CH = [
    (33, [57, 61, 64, 68, 71], [69, 73, 76, 80, 81, 76]),   # Amaj9
    (28, [56, 59, 64, 66, 71], [68, 71, 76, 78, 80, 76]),   # Eadd9/G#
    (30, [57, 61, 64, 68, 73], [69, 73, 76, 78, 81, 76]),   # F#m9
    (26, [57, 61, 62, 66, 69], [66, 69, 73, 74, 78, 73]),   # Dmaj9
]
def chord(bar): return CH[bar % 4]

# sections (bar indices, 0 based) -------------------------------------
NB = int(math.ceil(TOTAL / BAR))
_sp = [x for x in RF.SEQ if x[0] == 'spot']
b_spot1 = int(round(_sp[0][1] / BAR)); b_main2 = int(round((_sp[0][1] + _sp[0][2]) / BAR))
b_spot2 = int(round(_sp[1][1] / BAR)); b_main3 = int(round((_sp[1][1] + _sp[1][2]) / BAR))
b_outro = int(round([x for x in RF.SEQ if x[0] == 'outro'][0][1] / BAR))
VIG_BARS = set()
for x in RF.SEQ:
    if x[0] == 'vig':
        for bb in range(int(round(x[1] / BAR)), int(round((x[1] + x[2]) / BAR))): VIG_BARS.add(bb)
def section(b):
    if b < 4: return 'intro'
    if b in VIG_BARS: return 'break'
    if b < b_spot1: return 'main'
    if b < b_main2: return 'break'
    if b < b_spot2: return 'main'
    if b < b_main3: return 'break'
    if b < b_outro: return 'main'
    return 'outro'

# ------------------------------------------------------------------ instruments
def kick():
    n = int(0.45 * SR); t = np.arange(n) / SR
    f = 46 + 120 * np.exp(-t / 0.035) + 30 * np.exp(-t / 0.008)
    ph = 2 * np.pi * np.cumsum(f) / SR
    y = np.sin(ph) * np.exp(-t / 0.30) * (1 - np.exp(-t / 0.001))
    click = hp(rng.standard_normal(n).astype(np.float32), 3000) * np.exp(-t / 0.004) * 0.25
    return np.tanh((y + click) * 1.4).astype(np.float32) * 0.9

def clap():
    n = int(0.45 * SR); t = np.arange(n) / SR
    nz = bp(rng.standard_normal(n).astype(np.float32), 900, 3200)
    e = np.zeros(n, np.float32)
    for o in (0, 0.011, 0.022):
        tt = t - o; e += np.where(tt >= 0, np.exp(-np.clip(tt, 0, None) / 0.007), 0) * 0.6
    e += np.where(t >= 0.03, np.exp(-np.clip(t - 0.03, 0, None) / 0.11), 0)
    return (nz * e * 0.8).astype(np.float32)

def hat(open_=False):
    n = int((0.35 if open_ else 0.08) * SR); t = np.arange(n) / SR
    nz = hp(rng.standard_normal(n).astype(np.float32), 7500)
    return (nz * np.exp(-t / (0.09 if open_ else 0.022)) * 0.5).astype(np.float32)

def shaker():
    n = int(0.09 * SR); t = np.arange(n) / SR
    nz = bp(rng.standard_normal(n).astype(np.float32), 4500, 11000)
    e = (1 - np.exp(-t / 0.008)) * np.exp(-t / 0.03)
    return (nz * e * 0.5).astype(np.float32)

def pluck(m, dur=0.5, bright=1.0):
    f = mtof(m); n = int((dur + 0.1) * SR); t = np.arange(n) / SR
    y = np.zeros(n, np.float32)
    K = int(min(40, (SR * 0.4) // f))
    for k in range(1, K + 1):
        y += (1 / k) * np.sin(2 * np.pi * k * f * t + (k * 0.7)) * np.exp(-t * (3.2 + 2.4 * k / bright))
    y *= (1 - np.exp(-t / 0.002))
    rel = np.clip((t - dur) / 0.1, 0, 1); y *= (1 - rel)
    return (y * 0.35).astype(np.float32)

def bell(m, dur=1.4):
    f = mtof(m); n = int((dur + 0.5) * SR); t = np.arange(n) / SR
    idx = 2.2 * np.exp(-t * 5) + 0.25
    mod = np.sin(2 * np.pi * f * 3.5 * t) * idx
    y = np.sin(2 * np.pi * f * t + mod) * np.exp(-t * 1.9)
    y += 0.35 * np.sin(2 * np.pi * f * 2 * t + 0.5 * mod) * np.exp(-t * 3.5)
    y *= (1 - np.exp(-t / 0.002))
    return (y * 0.28).astype(np.float32)

def epiano(m, dur):
    f = mtof(m); n = int((dur + 0.8) * SR); t = np.arange(n) / SR
    idx = 1.4 * np.exp(-t * 4) + 0.15
    y = np.sin(2 * np.pi * f * t + idx * np.sin(2 * np.pi * f * t))
    y += 0.08 * np.sin(2 * np.pi * f * 14 * t) * np.exp(-t * 30)
    y *= np.exp(-t * 0.9) * (1 - np.exp(-t / 0.003))
    rel = np.clip((t - dur) / 0.6, 0, 1); y *= (1 - rel) ** 2
    return (y * 0.16).astype(np.float32)

def pad_note(m, dur, cutoff=2200):
    f = mtof(m); n = int((dur + 0.9) * SR)
    out = np.zeros((n, 2), np.float32)
    for j, (det, pan) in enumerate([(-0.12, -.8), (-0.05, -.35), (0, 0), (0.05, .35), (0.12, .8)]):
        y = polyblep_saw(f * 2 ** (det / 12), n, phase0=rng.random())
        l = math.cos((pan + 1) * math.pi / 4); r = math.sin((pan + 1) * math.pi / 4)
        out[:, 0] += y * l; out[:, 1] += y * r
    out = lp(out, cutoff)
    e = env_adsr(n, 0.35, 0.8, 0.8, 0.8, dur)
    return out * e[:, None] * 0.05

def bass_note(m, dur, sub=False):
    f = mtof(m); n = int((dur + 0.05) * SR); t = np.arange(n) / SR
    y = np.sin(2 * np.pi * f * t) + 0.3 * np.sin(4 * np.pi * f * t) + (0 if sub else 0.18 * polyblep_saw(f, n))
    y = np.tanh(y * 1.3)
    a = 0.004 if not sub else 0.08
    e = np.minimum(1, t / a) * np.clip((dur - t) / 0.03, 0, 1)
    if not sub: e *= np.exp(-t * 2.5) * 0.6 + 0.4
    return lp((y * e).astype(np.float32), 900 if not sub else 300) * 0.42

def riser(dur):
    n = int(dur * SR); t = np.arange(n) / SR; p = t / dur
    nz = rng.standard_normal(n).astype(np.float32)
    lo = hp(nz, 400); hi = hp(nz, 4000)
    y = lo * (1 - p) * 0.3 + hi * p * 0.7
    f = 200 * 2 ** (p * 3)
    y += 0.15 * np.sin(2 * np.pi * np.cumsum(f) / SR)
    return (y * p ** 2.2 * 0.35).astype(np.float32)

def impact():
    n = int(2.5 * SR); t = np.arange(n) / SR
    f = 30 + 50 * np.exp(-t / 0.15)
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.7)
    nz = lp(rng.standard_normal(n).astype(np.float32), 2500) * np.exp(-t / 0.25) * 0.4
    return ((y + nz) * 0.5).astype(np.float32)

def whoosh(dur=0.9, peak=0.55, f_lo=300, f_hi=5000, gain=1.0):
    n = int(dur * SR); t = np.arange(n) / SR; p = t / dur
    nz = rng.standard_normal(n).astype(np.float32)
    # time varying one pole lowpass (cutoff follows a bump)
    bump = np.exp(-((p - peak) / 0.22) ** 2)
    fc = f_lo + (f_hi - f_lo) * bump
    a = np.exp(-2 * np.pi * fc / SR).astype(np.float32)
    y = np.empty(n, np.float32); s = 0.0
    for i in range(n):
        s = a[i] * s + (1 - a[i]) * nz[i]; y[i] = s
    y = hp(y, 150) * bump * gain
    return y * 0.9

# ------------------------------------------------------------------ arrange
drums = buf(); bass = buf(); pads = buf(); arp = buf(); lead = buf(); keys = buf(); fx = buf()
KICK, CLAP, CH_, OH, SH = kick(), clap(), hat(), hat(True), shaker()
sc_times = []  # kick times for sidechain

MEL_A = [  # (beat, midi, len beats) over 4 bars
    [(0, 76, 1), (0.75, 73, .75), (1.5, 76, 1), (2.5, 78, .5), (3, 76, 1)],
    [(0, 71, 1), (0.75, 68, .75), (1.5, 71, 1), (2.5, 73, .5), (3.5, 71, .5)],
    [(0, 69, 1), (0.75, 73, .75), (1.5, 76, 1), (2.5, 78, .5), (3, 76, 1)],
    [(0, 78, 1), (0.75, 76, .75), (1.5, 73, 1.5), (3, 69, 1)],
]
MEL_B = [
    [(0, 81, 1), (1, 80, .5), (1.5, 76, 1), (2.5, 78, .5), (3, 80, 1)],
    [(0, 76, 1.5), (1.5, 73, .5), (2, 71, 1), (3, 73, 1)],
    [(0, 76, 1), (0.75, 78, .75), (1.5, 81, 1), (2.5, 80, .5), (3, 78, 1)],
    [(0, 78, 1.5), (1.5, 76, .5), (2, 73, 1), (3, 76, 1)],
]
ARP_PAT = [0, 2, 1, 3, 2, 4, 1, 5, 0, 2, 1, 3, 2, 4, 3, 5]

for b in range(NB):
    t0 = b * BAR
    if t0 >= TOTAL: break
    sec = section(b)
    root, voicing, arpn = chord(b)
    nxt = section(b + 1)
    final = sec == 'outro'
    # ---- pads
    if not (final and b > b_outro + 2):
        cut = 900 + 1700 * min(1, b / 4) if sec == 'intro' else (1600 if sec == 'break' else 2400)
        for m in voicing:
            add(pads, t0, pad_note(m, BAR if not (final and b == b_outro + 2) else 8.0, cut))
    # ---- drums
    if sec == 'main':
        for k in range(4):
            tk = t0 + k * BEAT; add(drums, tk, KICK, 0.72); sc_times.append(tk)
            add(drums, tk + BEAT / 2, CH_, 0.7, 0.25)
            for s_ in range(4):
                add(drums, tk + s_ * S16, SH, 0.24 + (0.1 if s_ == 2 else 0), -0.4)
        clap_on = not (b < 8 and b < b_spot1 and b >= 4)
        if clap_on:
            add(drums, t0 + BEAT, CLAP, 0.55, 0.05); add(drums, t0 + 3 * BEAT, CLAP, 0.55, 0.05)
        if b % 2 == 1: add(drums, t0 + 3.5 * BEAT, OH, 0.3, 0.3)
        if nxt != 'main' and b + 1 < NB:   # fill
            for s_ in range(8): add(drums, t0 + 2 * BEAT + s_ * S16, CLAP, 0.12 + 0.05 * s_, 0.1)
    elif sec == 'break':
        for k in range(4):
            tk = t0 + k * BEAT
            add(drums, tk + BEAT / 2, CH_, 0.28, 0.25)
            for s_ in range(4): add(drums, tk + s_ * S16, SH, 0.13, -0.4)
        if b % 2 == 0: add(drums, t0, KICK, 0.45); sc_times.append(t0)
        add(drums, t0 + 2 * BEAT, KICK, 0.30); sc_times.append(t0 + 2 * BEAT)
    elif sec == 'intro' and b >= 2:
        for k in range(4):
            for s_ in range(4): add(drums, t0 + k * BEAT + s_ * S16, SH, 0.06 * (b - 1), -0.4)
    elif final and b == b_outro:
        add(fx, t0, impact(), 0.8)
    # ---- bass
    if sec == 'main':
        for k in range(4):
            add(bass, t0 + k * BEAT + BEAT / 2, bass_note(root + 12, BEAT * 0.42))
            if k in (1, 3): add(bass, t0 + k * BEAT + 0.75 * BEAT, bass_note(root + 12, BEAT * 0.2), 0.6)
    elif sec == 'break':
        add(bass, t0, bass_note(root + 12, BAR * 0.95, sub=True), 0.8)
    elif final and b <= b_outro + 2:
        add(bass, t0, bass_note(root + 12, (BAR if b < b_outro + 2 else 6.0), sub=True), 0.8)
    # ---- arp pluck
    if sec in ('main', 'intro') or (sec == 'break' and (b - b_spot1) % 8 >= 4) or (final and b <= b_outro + 1):
        bright = 0.5 + 0.5 * min(1, b / 4) if sec == 'intro' else 1.0
        g = 0.55 if sec == 'main' else 0.42
        for s_ in range(16):
            m = arpn[ARP_PAT[s_] % len(arpn)]
            acc = 1.0 if s_ % 4 == 0 else 0.7
            add(arp, t0 + s_ * S16, pluck(m, S16 * 1.6, bright), g * acc, 0.35 if s_ % 2 else -0.35)
    # ---- melody (bell)
    mel = None
    if sec == 'main':
        local = b - (4 if b < b_spot1 else b_main2 if b < b_spot2 else b_main3)
        if (b < b_spot1 and 8 <= local < 24) or (b_main2 <= b < b_spot2 and local < 24) or (b >= b_main3):
            mel = (MEL_A if (local // 8) % 2 == 0 else MEL_B)[b % 4]
    elif final and b <= b_outro + 1:
        mel = MEL_A[b % 4]
    elif sec == 'break' and (b - (b_spot1 if b < b_main2 else b_spot2)) >= 8 and (b % 8) < 4:
        mel = MEL_A[b % 4]
    if mel:
        for (bt, m, ln) in mel:
            add(lead, t0 + bt * BEAT, bell(m, ln * BEAT + 0.3), 0.55 if sec != 'break' else 0.35)
    if final and b == b_outro + 2:
        add(lead, t0, bell(81, 5.0), 0.45); add(lead, t0, bell(76, 5.0), 0.3)
    # ---- e-piano in breaks
    if sec == 'break' or (final and b <= b_outro + 2):
        for j, bt in enumerate((0, 1.5, 2.5) if sec == 'break' else (0,)):
            for m in voicing[1:]:
                add(keys, t0 + bt * BEAT, epiano(m, 0.9 if sec == 'break' else 5.0), 0.8, rng.uniform(-.3, .3))
    # ---- risers into sections
    if nxt in ('main',) and sec in ('intro', 'break') and (b + 1) * BAR < TOTAL:
        add(fx, t0, riser(BAR), 0.6, 0.0)
    if sec in ('intro', 'break') and nxt == 'main':
        add(fx, (b + 1) * BAR, impact(), 0.45)

# ---- SFX synced to picture: page slides, card flights, wipes
for sc in RF.SEQ:
    if sc[0] == 'pages':
        st = sc[1]
        for idx, (pi, ps) in enumerate(sc[3]):
            if idx > 0: add(fx, st + ps - 0.15, whoosh(1.4, 0.45, 200, 3500, 1.0), 0.35, 0.0)
            nc = len(R.PAGES[pi]['cards'])
            for ci in range(nc):
                c0 = 2.0 if pi == 0 else 2.0 + 4.0 * ci
                add(fx, st + ps + c0 - 0.05, whoosh(0.95, 0.4, 500, 7000, 1.0), 0.16, 0.4)
for b in range(1, len(RF.SEQ)):
    tb = RF.SEQ[b][1]
    add(fx, tb - 0.6, whoosh(1.3, 0.5, 250, 6000, 1.0), 0.45, -0.2)

# ---- vignette foley
def splash(dur=1.2, bright=1.0):
    n = int(dur * SR); t = np.arange(n) / SR
    nz = rng.standard_normal(n).astype(np.float32)
    y = bp(nz, 400, 6000 * bright) * np.exp(-t / 0.18) * (1 - np.exp(-t / 0.003))
    y += lp(nz, 900) * np.exp(-t / 0.35) * 0.6
    for k in range(14):
        tk = rng.uniform(0.05, 0.9); f = rng.uniform(900, 2600); i = int(tk * SR); m = int(0.06 * SR)
        if i + m < n: y[i:i + m] += np.sin(2 * np.pi * f * np.arange(m) / SR * (1 + np.arange(m) / m)) * np.exp(-np.arange(m) / SR / 0.015) * 0.25
    return y.astype(np.float32) * 0.7
def crackle(dur=1.4):
    n = int(dur * SR); y = np.zeros(n, np.float32)
    for k in range(90):
        i = int(rng.uniform(0, dur - 0.02) * SR); m = int(0.01 * SR)
        y[i:i + m] += hp(rng.standard_normal(m).astype(np.float32), 3000) * np.exp(-np.arange(m) / SR / 0.002) * rng.uniform(0.2, 1)
    env = np.minimum(1, np.arange(n) / (0.3 * SR)) * np.clip((n - np.arange(n)) / (0.4 * SR), 0, 1)
    return y * env * 0.8
def thud():
    n = int(0.8 * SR); t = np.arange(n) / SR
    y = np.sin(2 * np.pi * np.cumsum(60 + 80 * np.exp(-t / 0.03)) / SR) * np.exp(-t / 0.18)
    y += lp(rng.standard_normal(n).astype(np.float32), 1500) * np.exp(-t / 0.05) * 0.4
    return y.astype(np.float32) * 0.8
def plink(f=1800):
    n = int(0.3 * SR); t = np.arange(n) / SR
    return (np.sin(2 * np.pi * np.cumsum(f * (1 + 0.6 * np.exp(-t / 0.02))) / SR) * np.exp(-t / 0.06) * 0.35).astype(np.float32)
def click():
    n = int(0.08 * SR); t = np.arange(n) / SR
    return (bp(rng.standard_normal(n).astype(np.float32), 1500, 5000) * np.exp(-t / 0.008) + np.sin(2 * np.pi * 900 * t) * np.exp(-t / 0.01) * 0.5).astype(np.float32)
def blip(f0=800, f1=1500):
    n = int(.22 * SR); t = np.arange(n) / SR
    f = f0 + (f1 - f0) * (1 - np.exp(-t / .02))
    return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / .07) * (1 - np.exp(-t / .002)) * .5).astype(np.float32)
import essere as ES
def clink(f=2400):
    n = int(0.35 * SR); t = np.arange(n) / SR
    y = sum(np.sin(2 * np.pi * f * r * t) * np.exp(-t / d) * g for r, d, g in ((1, .09, .5), (2.76, .05, .3), (5.4, .03, .2)))
    return (y * (1 - np.exp(-t / .001)) * .5).astype(np.float32)
def pop():
    n = int(0.3 * SR); t = np.arange(n) / SR
    return (bp(rng.standard_normal(n).astype(np.float32), 300, 4000) * np.exp(-t / 0.03) * 1.2 + np.sin(2 * np.pi * 180 * t) * np.exp(-t / 0.05) * 0.6).astype(np.float32)
for x in RF.SEQ:
    if x[0] == 'spot' and x[3]['key'] == 'card':
        st = x[1]
        add(fx, st + 0.2, whoosh(1.6, 0.4, 250, 6000, 1.0), 0.5)
        add(fx, st + 1.85, whoosh(1.2, 0.5, 2000, 12000, 1.0), 0.18, 0.3)
        for t0, _ in ES.COINS: add(fx, st + t0 + 0.72, clink(2300 + 120 * (int(t0 * 10) % 4)), 0.45, 0.2)
        for sx in (ES.S2, ES.S3, ES.S4, ES.S5, ES.S6): add(fx, st + sx - 0.45, whoosh(1.1, 0.45, 300, 5000, 1.0), 0.35, -0.2)
        add(fx, st + ES.S3 + 1.85, pop(), 0.7); add(fx, st + ES.S3 + 1.9, splash(0.8, 1.4) * 0.3, 0.6)
        for k in range(3): add(fx, st + ES.S4 + 0.6 + 0.25 * k + 0.3, blip(900 + 150 * k, 1600 + 150 * k), 0.35, -0.4 + 0.4 * k)
        for k in range(3): add(fx, st + ES.S5 + 0.6 + 0.3 * k + 0.25, blip(800 + 150 * k, 1500 + 150 * k), 0.35, -0.4 + 0.4 * k)
for x in RF.SEQ:
    if x[0] == 'anniv':
        add(fx, x[1] + 0.1, whoosh(1.0, 0.4, 400, 6000, 1.0), 0.3)
        for k in range(3): add(fx, x[1] + 0.25 + 0.18 * k + 0.55, blip(800 + 120 * k, 1500 + 160 * k), 0.4, -0.4 + 0.4 * k)
for x in RF.SEQ:
    if x[0] != 'vig': continue
    st = x[1]
    if x[3] == 'fish':
        add(fx, st + 1.40, splash(1.3), 0.9)
        add(fx, st + 3.05, crackle(1.4), 0.7, 0.2)
        add(fx, st + 3.85, whoosh(1.2, 0.5, 400, 9000, 1.0), 0.5)
        add(fx, st + 4.70 + 0.92, thud(), 0.8)
        add(fx, st + 4.70 + 0.92, whoosh(1.5, 0.2, 300, 4000, 1.0), 0.3)
    elif x[3] == 'cornetto':
        add(fx, st + 0.5, whoosh(1.2, 0.6, 300, 3000, 1.0), 0.3)
        add(fx, st + 1.93, splash(1.0, 0.6), 0.75)
        for k in range(8): add(fx, st + 3.25 + k * 0.16 + 0.25, plink(1500 + 150 * (k % 3)), 0.35, 0.1)
    elif x[3] == 'freezer':
        add(fx, st + 1.05, click(), 0.8, 0.3)
        add(fx, st + 1.1, whoosh(1.6, 0.4, 200, 2500, 1.0), 0.5, 0.3)
        add(fx, st + 1.4, hp(rng.standard_normal(int(3 * SR)).astype(np.float32), 5000) * np.sin(np.linspace(0, np.pi, int(3 * SR))) * 0.12, 1.0)
        for k in range(6): add(fx, st + 2.2 + 0.18 * k + 0.1, plink(1200 + 200 * k), 0.3, -0.3 + 0.12 * k)

# ------------------------------------------------------------------ sidechain
sc = np.ones(N, np.float32)
tt = np.arange(int(BEAT * SR)) / SR
duck = 1 - 0.55 * np.exp(-tt / 0.11) * (1 - np.exp(-tt / 0.004))
for tk in sc_times:
    i = int(tk * SR); n = min(len(duck), N - i)
    sc[i:i + n] = np.minimum(sc[i:i + n], duck[:n])
for bus in (pads, bass, arp, keys):
    bus *= sc[:, None]

# ------------------------------------------------------------------ fx: delay + reverb
def pingpong(x, d=0.375, fb=0.35, mix=0.28):
    D = int(d * SR); y = x.copy(); tap = x.copy()
    for k in range(1, 6):
        tap = np.roll(tap, D, axis=0); tap[:D] = 0; tap = tap[:, ::-1] * fb
        tap = lp(tap, 5000)
        y += tap * mix / fb * fb
    return y
arp = pingpong(arp, 0.375, 0.38, 0.6)
lead = pingpong(lead, 0.375, 0.32, 0.5)

def reverb_ir(sec_=2.4):
    n = int(sec_ * SR); t = np.arange(n) / SR
    ir = rng.standard_normal((n, 2)).astype(np.float32) * np.exp(-t / (sec_ / 6.9) * 1.0)[:, None]
    ir = lp(ir, 7000); ir[: int(0.012 * SR)] *= np.linspace(0, 1, int(0.012 * SR))[:, None]
    return ir / np.sqrt((ir ** 2).sum(0, keepdims=True))
IR = reverb_ir()
send = pads * 0.25 + arp * 0.35 + lead * 0.6 + keys * 0.5 + drums * 0.08 + fx * 0.4
send = hp(send, 250)
wet = np.stack([signal.fftconvolve(send[:, c], IR[:, c])[:N] for c in range(2)], 1).astype(np.float32)

ib = np.ones(N, np.float32); i8 = int(8 * SR); ib[:i8] = 2.0; ib[i8:i8 + SR // 2] = np.linspace(2.0, 1, SR // 2)
mix = drums * 1.0 + bass * 0.85 + pads * 1.7 * ib[:, None] + arp * 1.05 * ib[:, None] + lead * 1.4 + keys * 1.3 + fx * 0.8 + wet * 0.45
mix = hp(mix, 28)
# end fade, tail cut at TOTAL
n_end = int(TOTAL * SR)
fade = np.ones(N, np.float32); f0 = int((TOTAL - 3.0) * SR)
fade[f0:n_end] = np.linspace(1, 0, n_end - f0) ** 1.5; fade[n_end:] = 0
mix *= fade[:, None]
# gentle start fade-in (5 ms) for clean loop
mix[: int(0.005 * SR)] *= np.linspace(0, 1, int(0.005 * SR))[:, None]
mix = mix[:n_end]
peak = np.abs(mix).max(); mix = mix / peak * 0.7
print('rms per bus', {k: float(np.sqrt((v ** 2).mean())) for k, v in dict(drums=drums, bass=bass, pads=pads, arp=arp, lead=lead, keys=keys, fx=fx).items()})
import wave
pcm = (np.clip(mix, -1, 1) * 32767).astype(np.int16)
with wave.open(os.path.dirname(os.path.abspath(__file__)) + '/out/music_final_raw.wav', 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
print('ok', len(mix) / SR)
