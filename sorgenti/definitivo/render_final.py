#!/usr/bin/env python3
"""DEFINITIVE Superfreddo video = version A + illustrated vignettes, multi-store (no store address).
usage: render_final.py info | frame <prefix> <t>... | chunk <i> <n> <out.mp4> [a b]"""
import os, sys, time, subprocess
_argv = sys.argv; sys.argv = ['x']
import render as R
sys.argv = _argv
import numpy as np
from PIL import Image
import vignettes as V

# ---------------- timeline
SEQ = []; t = 0.0
def add(kind, dur, payload=None):
    global t
    SEQ.append((kind, t, dur, payload)); t += dur
def block(pages):
    sched = []; t0 = 0.0
    for p in pages: sched.append((p, t0)); t0 += R.page_dur(p)
    add('pages', t0, sched)
add('intro', R.INTRO)
block([0])
add('vig', 8.0, 'fish')
block([1, 2, 3])
add('spot', R.SPOT1['dur'], R.SPOT1)
block([4])
add('vig', 8.0, 'cornetto')
block([5])
add('vig', 8.0, 'freezer')
block([6])
add('spot', R.SPOT2['dur'], R.SPOT2)
block([7])
add('outro', R.OUTRO)
TOTAL = t
R.SEQ = SEQ; R.TOTAL = TOTAL

# ---------------- multi-store: no store marks
for pg in R.PAGES: pg.pop('mark', None)

_orig_scene_draw = R.scene_draw
def scene_draw(cv, sc, tg):
    if sc[0] == 'vig':
        cv[:] = V.render_vig(sc[3], tg - sc[1]); return
    _orig_scene_draw(cv, sc, tg)
R.scene_draw = scene_draw

def setup():
    R.setup()
    ts = R.text_sprite
    R.AS.foot_store = ts("SCARICA L'APP DECÒ", 46, 600, (169, 211, 240), track=6)
    R.AS.t_wait = ts('LE OFFERTE TI ASPETTANO', 60, 600, (169, 211, 240), track=12)
    R.AS.t_city = ts('NEI PUNTI VENDITA', 132, 800, (255, 255, 255), track=4)
    R.AS.t_addr = ts('DECÒ SUPERFREDDO', 96, 700, (159, 208, 242), track=8)

def to8(f): return (np.clip(f, 0, 1) * 255 + 0.5).astype(np.uint8)

if __name__ == '__main__':
    mode = sys.argv[1]
    if mode == 'info':
        for s in SEQ: print(f'{s[1]:7.2f} {s[2]:6.2f} {s[0]} {s[3] if s[0] == "vig" else ""}')
        print('TOTAL', TOTAL); sys.exit()
    setup()
    if mode == 'frame':
        os.makedirs(os.path.dirname(sys.argv[2]) or '.', exist_ok=True)
        for tt in sys.argv[3:]:
            Image.fromarray(to8(R.render(float(tt)))).save(f'{sys.argv[2]}_{float(tt):07.2f}.png')
    elif mode == 'chunk':
        i, n, out = int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
        N = int(round(TOTAL * R.FPS)); a = N * i // n; b = N * (i + 1) // n
        if len(sys.argv) > 6: a, b = int(sys.argv[5]), int(sys.argv[6])
        W, H, FPS = R.W, R.H, R.FPS
        enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                                '-c:v', 'libx264', '-preset', 'medium', '-crf', '14', '-maxrate', '60M', '-bufsize', '120M',
                                '-profile:v', 'high', '-level', '5.1', '-pix_fmt', 'yuv420p', '-g', '50', '-keyint_min', '50', '-sc_threshold', '0',
                                '-x264-params', 'threads=2:rc-lookahead=15', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709',
                                '-vf', 'scale=out_color_matrix=bt709:out_range=tv', out], stdin=subprocess.PIPE)
        t0 = time.time()
        for fi in range(a, b):
            enc.stdin.write(to8(R.render(fi / FPS)).tobytes())
            if (fi - a) % 50 == 0: print(f'chunk {i}: {fi - a}/{b - a} {time.time() - t0:.0f}s', flush=True)
        enc.stdin.close(); enc.wait(); print('done', i, flush=True)
