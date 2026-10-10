#!/usr/bin/env python3
"""Original track for VERSION B: sunny acoustic-pop, 120 BPM, D major.
Sampled instruments (FluidR3 GM, MIT licence) rendered with fluidsynth + synthesised drums/bass/fx."""
import os, sys, math, subprocess, wave
import numpy as np
from scipy import signal
import mido
D = os.path.dirname(os.path.abspath(__file__))
sys.argv = ['x']; sys.path.insert(0, D)
import render_b as RB

SR = 48000; BPM = 120; BEAT = 0.5; BAR = 2.0; S16 = BEAT / 4
TOTAL = RB.TOTAL; N = int(TOTAL * SR) + SR * 6
SF2 = '/usr/share/sounds/sf2/FluidR3_GM.sf2'
OUT = D + '/outb/music'; os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(5)

# ------------------------------------------------------------- sections (bars)
def bar_of(t): return int(round(t / BAR))
sp1 = [s for s in RB.SHOTS if s['kind'] == 'spot']
b_spot1, b_main2 = bar_of(sp1[0]['start']), bar_of(sp1[0]['start'] + sp1[0]['dur'])
b_spot2, b_main3 = bar_of(sp1[1]['start']), bar_of(sp1[1]['start'] + sp1[1]['dur'])
b_outro = bar_of([s for s in RB.SHOTS if s['kind'] == 'outro'][0]['start'])
NB = int(math.ceil(TOTAL / BAR))
def section(b):
    if b < 4: return 'intro'
    if b < b_spot1: return 'main'
    if b < b_main2: return 'break'
    if b < b_spot2: return 'main'
    if b < b_main3: return 'break'
    if b < b_outro: return 'main'
    return 'outro'
print('bars', NB, b_spot1, b_main2, b_spot2, b_main3, b_outro)

# chords: (bass midi, voicing, arp tones)
CH = [(38, [62, 66, 69, 74], [74, 78, 81, 78, 74, 69, 74, 78]),        # D
      (37, [61, 64, 69, 73], [73, 76, 81, 76, 73, 69, 73, 76]),        # A/C#
      (35, [62, 66, 69, 71], [71, 74, 78, 74, 71, 66, 71, 74]),        # Bm7
      (31, [62, 67, 71, 74], [74, 79, 83, 79, 74, 71, 74, 79])]        # Gadd
MEL = [[(0, 81, .5), (.5, 78, .5), (1, 81, .5), (1.5, 83, 1), (2.5, 81, .5), (3, 78, 1)],
       [(0, 76, .5), (.5, 73, .5), (1, 76, .5), (1.5, 78, 1), (2.5, 76, 1.5)],
       [(0, 74, .5), (.5, 78, .5), (1, 83, 1), (2, 81, 1), (3, 78, 1)],
       [(0, 79, .5), (.5, 78, .5), (1, 76, 1), (2, 74, 1), (3, 76, 1)]]
MEL2 = [[(0, 86, 1), (1, 85, .5), (1.5, 83, 1), (2.5, 81, .5), (3, 83, 1)],
        [(0, 81, 1.5), (1.5, 78, .5), (2, 76, 1), (3, 78, 1)],
        [(0, 78, .5), (.5, 81, .5), (1, 86, 1), (2, 85, 1), (3, 83, 1)],
        [(0, 83, 1.5), (1.5, 81, .5), (2, 79, 1), (3, 78, 1)]]

# ------------------------------------------------------------- MIDI parts
TPB = 480
def tick(t): return max(0, int(round(t / BEAT * TPB)))
class Part:
    def __init__(self, prog, ch=0, name=''):
        self.ev = []; self.prog = prog; self.ch = ch; self.name = name
    def note(self, t, m, dur, vel):
        vel = int(max(1, min(127, vel)))
        self.ev.append((tick(t), 'on', m, vel)); self.ev.append((tick(t + dur), 'off', m, 0))
    def save(self, path, cc=None):
        mf = mido.MidiFile(ticks_per_beat=TPB); tr = mido.MidiTrack(); mf.tracks.append(tr)
        tr.append(mido.MetaMessage('set_tempo', tempo=500000))
        if self.ch != 9: tr.append(mido.Message('program_change', program=self.prog, channel=self.ch, time=0))
        tr.append(mido.Message('control_change', control=91, value=0, channel=self.ch, time=0))
        tr.append(mido.Message('control_change', control=93, value=0, channel=self.ch, time=0))
        ev = sorted(self.ev, key=lambda e: (e[0], 0 if e[1] == 'off' else 1)); last = 0
        for (tk, kind, m, v) in ev:
            tr.append(mido.Message('note_on' if kind == 'on' else 'note_off', note=m, velocity=v, channel=self.ch, time=tk - last)); last = tk
        mf.save(path)

piano = Part(0, 0, 'piano'); marim = Part(12, 1, 'marimba'); glock = Part(9, 2, 'glock'); pizz = Part(45, 3, 'pizz')
strings = Part(48, 4, 'strings'); perc = Part(0, 9, 'perc'); celesta = Part(8, 5, 'celesta')

for b in range(NB):
    t0 = b * BAR
    if t0 >= TOTAL: break
    sec = section(b); root, voi, arp = CH[b % 4]
    final = sec == 'outro'
    hum = lambda: rng.normal(0, 0.004)
    # strings pad: intro, breaks, outro
    if sec in ('intro', 'break') or final:
        if not (final and b > b_outro + 2):
            ln = BAR if not (final and b == b_outro + 2) else 7.0
            for m in voi[:3]: strings.note(t0, m - 12 if m > 66 else m, ln, 58 if sec != 'intro' else 40 + 6 * b)
    # piano
    if sec == 'main' or (sec == 'break'):
        hits = [(0, 1.4), (1.5, 0.9), (3, 0.9)] if sec == 'main' else [(0, 3.5)]
        for (bt, ln) in hits:
            for m in voi: piano.note(t0 + bt * BEAT + hum(), m, ln * BEAT, (78 if bt == 0 else 66) - (12 if sec == 'break' else 0))
            piano.note(t0 + bt * BEAT, root + 12, ln * BEAT, 70 - (12 if sec == 'break' else 0))
    if final and b <= b_outro + 2:
        for m in voi: piano.note(t0, m, BAR if b < b_outro + 2 else 6.5, 64)
        piano.note(t0, root + 12, BAR if b < b_outro + 2 else 6.5, 66)
    # marimba arpeggio 8ths
    if sec in ('main', 'intro') or (final and b <= b_outro + 1):
        for k in range(8):
            v = (92 if k % 2 == 0 else 74) if sec == 'main' else 50 + 8 * b
            marim.note(t0 + k * BEAT / 2 + hum(), arp[k], BEAT * 0.45, v)
    # pizzicato in breaks (offbeat)
    if sec == 'break':
        for k in range(4):
            pizz.note(t0 + k * BEAT + BEAT / 2, arp[(k * 2) % 8] - 12, BEAT * 0.4, 70)
            if (b % 2) == 1: pizz.note(t0 + k * BEAT, root + 24, BEAT * 0.4, 62)
    # melody
    mel = None
    if sec == 'main':
        if b < b_spot1: loc = b - 4; mel = (MEL if (loc // 8) % 2 == 0 else MEL2) if loc >= 8 else None
        elif b < b_spot2: loc = b - b_main2; mel = MEL if (loc // 8) % 2 == 0 else MEL2
        else: mel = MEL2
    elif final and b <= b_outro + 1: mel = MEL
    elif sec == 'break':
        loc = b - (b_spot1 if b < b_main2 else b_spot2)
        if 8 <= loc < 16: mel = MEL
    if mel:
        inst = glock if sec != 'break' else celesta
        for (bt, m, ln) in mel[b % 4]:
            inst.note(t0 + bt * BEAT, m, ln * BEAT, 92 if sec != 'break' else 70)
    if final and b == b_outro + 2:
        glock.note(t0, 86, 4, 80); glock.note(t0, 81, 4, 70)
    # GM percussion: shaker 82, tambourine 54, clap 39, snap? (none in GM -> use side stick 37)
    if sec == 'main':
        for k in range(16): perc.note(t0 + k * S16 + hum(), 82, S16, 64 if k % 2 else 46)
        for k in range(4): perc.note(t0 + k * BEAT + BEAT / 2, 54, S16, 58)
    elif sec == 'break':
        for k in range(8): perc.note(t0 + k * BEAT / 2, 82, S16, 40)
        perc.note(t0 + BEAT, 37, S16, 55); perc.note(t0 + 3 * BEAT, 37, S16, 55)
    elif sec == 'intro' and b >= 2:
        for k in range(16): perc.note(t0 + k * S16, 82, S16, 20 + 10 * b)

def render_part(p):
    mid = f'{OUT}/{p.name}.mid'; wav = f'{OUT}/{p.name}.wav'
    p.save(mid)
    subprocess.run(['fluidsynth', '-ni', '-g', '0.6', '-r', str(SR), '-R', '0', '-C', '0', '-F', wav, SF2, mid], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    with wave.open(wav) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).reshape(-1, 2).astype(np.float32) / 32768
    out = np.zeros((N, 2), np.float32); n = min(N, len(x)); out[:n] = x[:n]
    return out
stems = {p.name: render_part(p) for p in (piano, marim, glock, pizz, strings, perc, celesta)}

# ------------------------------------------------------------- synth drums / bass / fx
def buf(): return np.zeros((N, 2), np.float32)
def add(b, t, x, g=1.0, pan=0.0):
    i = int(round(t * SR))
    if i >= N or i < 0: return
    if x.ndim == 1:
        l = math.cos((pan + 1) * math.pi / 4); r = math.sin((pan + 1) * math.pi / 4)
        x = np.stack([x * l * 1.414, x * r * 1.414], 1)
    n = min(len(x), N - i); b[i:i + n] += x[:n] * g
def lp(x, fc): bb, aa = signal.butter(2, fc / (SR / 2), 'low'); return signal.lfilter(bb, aa, x, axis=0).astype(np.float32)
def hp(x, fc): bb, aa = signal.butter(2, fc / (SR / 2), 'high'); return signal.lfilter(bb, aa, x, axis=0).astype(np.float32)
def bp(x, a, c): bb, aa = signal.butter(2, [a / (SR / 2), c / (SR / 2)], 'band'); return signal.lfilter(bb, aa, x, axis=0).astype(np.float32)
def kick():
    n = int(.4 * SR); t = np.arange(n) / SR
    f = 50 + 95 * np.exp(-t / .03) + 40 * np.exp(-t / .006)
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / .22)
    y += hp(rng.standard_normal(n).astype(np.float32), 2500) * np.exp(-t / .003) * .2
    return np.tanh(y * 1.3).astype(np.float32) * .85
def clap():
    n = int(.4 * SR); t = np.arange(n) / SR
    nz = bp(rng.standard_normal(n).astype(np.float32), 1000, 3500); e = np.zeros(n, np.float32)
    for o in (0, .01, .021): tt = t - o; e += np.where(tt >= 0, np.exp(-np.clip(tt, 0, None) / .006), 0) * .6
    e += np.where(t >= .028, np.exp(-np.clip(t - .028, 0, None) / .09), 0)
    return nz * e * .8
def snap():
    n = int(.15 * SR); t = np.arange(n) / SR
    nz = bp(rng.standard_normal(n).astype(np.float32), 1800, 6000)
    return (nz * np.exp(-t / .012) * .9 + np.sin(2 * np.pi * 1700 * t) * np.exp(-t / .008) * .3).astype(np.float32)
def bassn(m, dur):
    f = 440 * 2 ** ((m - 69) / 12); n = int((dur + .05) * SR); t = np.arange(n) / SR
    y = np.sin(2 * np.pi * f * t) + .25 * np.sin(4 * np.pi * f * t) + .08 * np.sin(6 * np.pi * f * t)
    e = np.minimum(1, t / .005) * np.clip((dur - t) / .04, 0, 1) * (0.55 + 0.45 * np.exp(-t * 3))
    return lp(np.tanh(y * 1.2) * e, 700).astype(np.float32) * .5
def whoosh(dur, peak, flo, fhi):
    n = int(dur * SR); t = np.arange(n) / SR; p = t / dur
    nz = rng.standard_normal(n).astype(np.float32); bump = np.exp(-((p - peak) / .22) ** 2)
    fc = flo + (fhi - flo) * bump; a = np.exp(-2 * np.pi * fc / SR).astype(np.float32)
    y = np.empty(n, np.float32); s = 0.0
    for i in range(n): s = a[i] * s + (1 - a[i]) * nz[i]; y[i] = s
    return hp(y, 150) * bump
def blip(f0=700, f1=1400):
    n = int(.22 * SR); t = np.arange(n) / SR
    f = f0 + (f1 - f0) * (1 - np.exp(-t / .02))
    return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / .07) * (1 - np.exp(-t / .002)) * .5).astype(np.float32)
def riser(dur):
    n = int(dur * SR); t = np.arange(n) / SR; p = t / dur
    nz = rng.standard_normal(n).astype(np.float32)
    y = hp(nz, 500) * (1 - p) * .3 + hp(nz, 4000) * p * .7
    return (y * p ** 2.2 * .35).astype(np.float32)
def impact():
    n = int(2.2 * SR); t = np.arange(n) / SR
    y = np.sin(2 * np.pi * np.cumsum(32 + 45 * np.exp(-t / .12)) / SR) * np.exp(-t / .6)
    return ((y + lp(rng.standard_normal(n).astype(np.float32), 2000) * np.exp(-t / .2) * .35) * .5).astype(np.float32)

drums = buf(); bass = buf(); fx = buf(); KICK, CLAP, SNAP = kick(), clap(), snap()
sc_t = []
for b in range(NB):
    t0 = b * BAR
    if t0 >= TOTAL: break
    sec = section(b); root = CH[b % 4][0]; nxt = section(b + 1)
    if sec == 'main':
        for bt in (0, 1.5, 2, 3.5 if b % 2 else 3):
            add(drums, t0 + bt * BEAT, KICK, .8); sc_t.append(t0 + bt * BEAT)
        add(drums, t0 + BEAT, CLAP, .5); add(drums, t0 + 3 * BEAT, CLAP, .5)
        add(drums, t0 + BEAT, SNAP, .25, .3); add(drums, t0 + 3 * BEAT, SNAP, .25, .3)
        for (bt, ln) in ((0, 1.3), (1.5, .4), (2, .9), (3.5, .4)):
            add(bass, t0 + bt * BEAT, bassn(root + 12, ln * BEAT), 1.0)
        if nxt != 'main' and b + 1 < NB:
            for k in range(6): add(drums, t0 + 2.5 * BEAT + k * S16, SNAP, .1 + .05 * k)
    elif sec == 'break':
        add(drums, t0 + BEAT, SNAP, .35, .3); add(drums, t0 + 3 * BEAT, SNAP, .35, .3)
        add(bass, t0, bassn(root + 12, BAR * .9), .6)
        if b % 2 == 0: add(drums, t0, KICK, .4); sc_t.append(t0)
    elif sec == 'outro' and b <= b_outro + 2:
        add(bass, t0, bassn(root + 12, BAR if b < b_outro + 2 else 6), .6)
        if b == b_outro: add(fx, t0, impact(), .6)
    if sec in ('intro', 'break') and nxt == 'main' and (b + 1) * BAR < TOTAL:
        add(fx, t0, riser(BAR), .55); add(fx, (b + 1) * BAR, impact(), .4)

# picture-synced fx
for i, s in enumerate(RB.SHOTS):
    if i > 0 and s['tr'] not in (None, 'none'):
        add(fx, s['start'] - 0.55, whoosh(1.2, .45, 300, 6500), .42, .2)
    if s['kind'] == 'hero':
        add(fx, s['start'] - 0.1, whoosh(0.9, .35, 500, 7000), .16, -.3)
        if s['h']['kind'] == 'trio':
            for k in range(3): add(fx, s['start'] + 0.25 + 0.18 * k + 0.6, blip(800 + 120 * k, 1500 + 160 * k), .22)
        else:
            add(fx, s['start'] + 0.78, blip(), .25)
    if s['kind'] == 'scroll':
        add(fx, s['start'] + 0.0, whoosh(1.6, .4, 200, 3500), .25)

# sidechain (gentle)
sc = np.ones(N, np.float32); tt = np.arange(int(BEAT * SR)) / SR
duck = 1 - .35 * np.exp(-tt / .1) * (1 - np.exp(-tt / .004))
for t_ in sc_t:
    i = int(t_ * SR); n = min(len(duck), N - i); sc[i:i + n] = np.minimum(sc[i:i + n], duck[:n])

# reverb
def ir(sec_=2.0):
    n = int(sec_ * SR); t = np.arange(n) / SR
    x = rng.standard_normal((n, 2)).astype(np.float32) * np.exp(-t / (sec_ / 6.9))[:, None]
    x = lp(x, 6500); x[:int(.01 * SR)] *= np.linspace(0, 1, int(.01 * SR))[:, None]
    return x / np.sqrt((x ** 2).sum(0, keepdims=True))
IR = ir()
st = stems
dry = (st['piano'] * 1.0 + st['marimba'] * 0.9 + st['glock'] * 0.85 + st['celesta'] * 0.8 + st['pizz'] * 0.9 + st['strings'] * 0.75 + st['perc'] * 0.7)
ib = np.ones(N, np.float32); i8 = int(8 * SR); ib[:i8] = 2.4; ib[i8:i8 + SR // 2] = np.linspace(2.4, 1, SR // 2)
br = np.ones(N, np.float32)
for b in range(NB):
    if section(b) == 'break': br[int(b * BAR * SR):int((b + 1) * BAR * SR)] = 1.45
br = np.convolve(br, np.ones(4800) / 4800, mode='same').astype(np.float32)
dry = dry * 2.3 * (ib * br)[:, None] * sc[:, None] + bass * 0.9 * sc[:, None] + drums * 0.85 + fx * 0.8
send = 2.3 * hp(st['piano'] * .25 + st['marimba'] * .3 + st['glock'] * .45 + st['celesta'] * .5 + st['strings'] * .4 + st['pizz'] * .3 + drums * .06 + fx * .3, 250)
wet = np.stack([signal.fftconvolve(send[:, c], IR[:, c])[:N] for c in range(2)], 1).astype(np.float32)
mix = hp(dry + wet * .5, 30)
n_end = int(TOTAL * SR); f0 = int((TOTAL - 3) * SR)
fade = np.ones(N, np.float32); fade[f0:n_end] = np.linspace(1, 0, n_end - f0) ** 1.5; fade[n_end:] = 0
mix = (mix * fade[:, None])[:n_end]
mix[:int(.005 * SR)] *= np.linspace(0, 1, int(.005 * SR))[:, None]
mix = mix / np.abs(mix).max() * .7
for k, v in stems.items(): print(k, round(float(np.sqrt((v ** 2).mean())), 4))
pcm = (np.clip(mix, -1, 1) * 32767).astype(np.int16)
with wave.open(D + '/outb/music_b_raw.wav', 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
print('ok', len(mix) / SR)
