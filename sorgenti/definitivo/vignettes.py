#!/usr/bin/env python3
"""Hand-built illustrated animations (cairo vector + numpy fx) for the definitive Superfreddo video.
render_vig(name, t) -> float32 HxWx3 (0..1).   usage: vignettes.py <name> <t>...  (writes test PNGs)"""
import os, sys, math
import numpy as np, cv2, cairo
from PIL import Image, ImageDraw, ImageFont

S = os.path.dirname(os.path.abspath(__file__))
W, H = 3840, 2160
FONT = {w: S + f'/fonts/Jost-{w}.ttf' for w in (400, 500, 600, 700, 800, 900)}
rng0 = np.random.default_rng(42)

def hx(h, a=1.0):
    h = h.lstrip('#'); return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255, a)
def clamp(x, a=0., b=1.): return a if x < a else b if x > b else x
def lerp(a, b, t): return a + (b - a) * t
def prog(t, t0, d): return clamp((t - t0) / d)
def e_io3(x): return 4 * x * x * x if x < .5 else 1 - (-2 * x + 2) ** 3 / 2
def e_o3(x): return 1 - (1 - x) ** 3
def e_o5(x): return 1 - (1 - x) ** 5
def e_i2(x): return x * x
def e_i3(x): return x ** 3
def e_oback(x, s=1.4): x -= 1; return 1 + (s + 1) * x ** 3 + s * x ** 2
def mix(c1, c2, t): return tuple(lerp(a, b, t) for a, b in zip(c1, c2))

# ------------------------------------------------------------------ cairo helpers
def new_surface(w=W, h=H):
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    c = cairo.Context(s); c.set_antialias(cairo.ANTIALIAS_BEST)
    return s, c

def surf_rgba(s):
    """premultiplied float RGBA from cairo surface"""
    s.flush()
    a = np.ndarray((s.get_height(), s.get_width(), 4), np.uint8, s.get_data(), strides=(s.get_stride(), 4, 1))
    out = a[..., [2, 1, 0, 3]].astype(np.float32) / 255
    return out

def np_to_surface(rgba):
    """straight float RGBA -> cairo ImageSurface (premultiplied BGRA)"""
    h, w = rgba.shape[:2]
    pm = rgba.copy(); pm[..., :3] *= pm[..., 3:4]
    arr = np.zeros((h, w, 4), np.uint8)
    arr[..., 0] = pm[..., 2] * 255; arr[..., 1] = pm[..., 1] * 255; arr[..., 2] = pm[..., 0] * 255; arr[..., 3] = pm[..., 3] * 255
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    st = surf.get_stride()
    buf = np.ndarray((h, st // 4, 4), np.uint8, surf.get_data())
    buf[:, :w] = arr; surf.mark_dirty()
    return surf

def over(dst, src_pm, alpha=1.0):
    """dst RGB float, src premultiplied RGBA float same size"""
    a = src_pm[..., 3:4] * alpha
    dst *= 1 - a; dst += src_pm[..., :3] * alpha

def lin(c, x0, y0, x1, y1, stops):
    g = cairo.LinearGradient(x0, y0, x1, y1)
    for o, col in stops: g.add_color_stop_rgba(o, *col)
    c.set_source(g)

def rad(c, cx, cy, r0, r1, stops, cx1=None, cy1=None):
    g = cairo.RadialGradient(cx if cx1 is None else cx1, cy if cy1 is None else cy1, r0, cx, cy, r1)
    for o, col in stops: g.add_color_stop_rgba(o, *col)
    c.set_source(g)

def rrect(c, x, y, w, h, r):
    c.new_sub_path()
    c.arc(x + w - r, y + r, r, -math.pi / 2, 0); c.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    c.arc(x + r, y + h - r, r, math.pi / 2, math.pi); c.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    c.close_path()

def text_layer(txt, size, weight, color, track=0):
    f = ImageFont.truetype(FONT[weight], size)
    ws = [f.getlength(ch) for ch in txt]; tw = int(sum(ws) + track * (len(txt) - 1)) + 20
    asc, desc = f.getmetrics()
    im = Image.new('RGBA', (tw, asc + desc + 20), (0, 0, 0, 0)); d = ImageDraw.Draw(im); x = 10
    for ch, wd in zip(txt, ws): d.text((x, 10), ch, font=f, fill=color); x += wd + track
    im = im.crop(im.getbbox())
    a = np.asarray(im, np.float32) / 255
    return a  # straight RGBA

def blit(dst, rgba, cx, cy, alpha=1.0, scale=1.0):
    """straight RGBA sprite onto RGB float dst, centred, integer-ish placement with cv2 resize when scaled"""
    if alpha <= 0: return
    if abs(scale - 1) > 1e-3:
        rgba = cv2.resize(rgba, (max(1, int(rgba.shape[1] * scale)), max(1, int(rgba.shape[0] * scale))), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC)
        rgba = np.clip(rgba, 0, 1)
    h, w = rgba.shape[:2]
    x0 = int(round(cx - w / 2)); y0 = int(round(cy - h / 2))
    X0, Y0, X1, Y1 = max(0, x0), max(0, y0), min(dst.shape[1], x0 + w), min(dst.shape[0], y0 + h)
    if X1 <= X0 or Y1 <= Y0: return
    s = rgba[Y0 - y0:Y1 - y0, X0 - x0:X1 - x0]
    a = s[..., 3:4] * alpha
    roi = dst[Y0:Y1, X0:X1]; roi *= 1 - a; roi += s[..., :3] * a

def soft_blob(r):
    s = int(r * 2.4) | 1; yy, xx = np.mgrid[0:s, 0:s].astype(np.float32); c = s / 2
    d = np.sqrt((xx - c) ** 2 + (yy - c) ** 2) / r
    a = np.exp(-d * d * 2.2)
    return a

def add_glow(dst, cx, cy, r, col, a):
    blob = BLOBS.get(r)
    if blob is None:
        blob = soft_blob(r); BLOBS[r] = blob
    h, w = blob.shape; x0, y0 = int(cx - w / 2), int(cy - h / 2)
    X0, Y0, X1, Y1 = max(0, x0), max(0, y0), min(W, x0 + w), min(H, y0 + h)
    if X1 <= X0 or Y1 <= Y0: return
    b = blob[Y0 - y0:Y1 - y0, X0 - x0:X1 - x0][..., None] * a
    roi = dst[Y0:Y1, X0:X1]; roi *= 1 - b; roi += np.array(col[:3], np.float32) * b
BLOBS = {}

def load_rgba(p):
    return np.asarray(Image.open(p).convert('RGBA'), np.float32) / 255

def recolor(rgba, white_to, blue_to):
    k = np.clip((rgba[..., 0:1] - 150 / 255) / (105 / 255), 0, 1)
    out = rgba.copy(); out[..., :3] = np.array(white_to[:3]) * k + np.array(blue_to[:3]) * (1 - k)
    return out

# ------------------------------------------------------------------ shared assets
class A_: pass
AS = A_()
def assets():
    if hasattr(AS, 'ok'): return
    AS.ok = True
    AS.logo_sf_navy = recolor(load_rgba(S + '/assets/logo_superfreddo.png'), hx('16324a'), hx('2f86c8'))
    AS.logo_sf_white = load_rgba(S + '/assets/logo_superfreddo.png')
    # frost texture: fine dendritic crystals + cloudy base (built at 1920 then upscaled)
    n = 1920; rr = np.random.default_rng(3)
    im = Image.new('L', (n, n), 0); d = ImageDraw.Draw(im)
    def dend(x, y, L, a, depth, val):
        x2, y2 = x + L * math.cos(a), y + L * math.sin(a)
        d.line([(x, y), (x2, y2)], fill=val, width=1)
        if depth > 0:
            for f in (0.4, 0.7):
                bx, by = x + (x2 - x) * f, y + (y2 - y) * f
                for sg in (-1, 1): dend(bx, by, L * 0.38, a + sg * math.pi / 3, depth - 1, int(val * 0.8))
    for _ in range(2600):
        x, y = rr.random() * n, rr.random() * n; L = rr.uniform(4, 26) * (1 + 2 * rr.random() ** 6); a0 = rr.random() * math.pi
        for k in range(6): dend(x, y, L, a0 + k * math.pi / 3, 1, int(rr.uniform(70, 190)))
    fr = np.asarray(im, np.float32) / 255
    cloud = np.zeros((n, n), np.float32)
    for sc_, amp in ((8, .5), (24, .3), (80, .2)):
        cloud += amp * cv2.resize(rr.random((n // sc_ + 2, n // sc_ + 2)).astype(np.float32), (n, n), interpolation=cv2.INTER_CUBIC)[:n, :n]
    fr = np.clip(fr * 0.85 + cv2.GaussianBlur(fr, (0, 0), 3) * 1.4 + (cloud - 0.3) * 0.5, 0, 1)
    AS.frost = fr
    AS.frost_big = cv2.resize(fr[:1080 * 1920 // 1920 + 0, :1920], (W, H), interpolation=cv2.INTER_CUBIC)
    AS.frost_pat = np_to_surface(np.dstack([np.ones((n, n, 3), np.float32), fr * 0.8]))

# ================================================================== FISH
SEA = [hx('0e3150'), hx('124a75'), hx('1a6aa3'), hx('0d3a5f'), hx('082740')]

def fish_body(c):
    """orata in local coords: nose at (-1,0), tail base at (0.86,0). length ~2 units"""
    c.move_to(-1.0, 0.02)
    c.curve_to(-0.95, -0.22, -0.62, -0.46, -0.18, -0.50)
    c.curve_to(0.25, -0.52, 0.62, -0.30, 0.86, -0.09)
    c.line_to(0.86, 0.09)
    c.curve_to(0.60, 0.28, 0.25, 0.43, -0.20, 0.42)
    c.curve_to(-0.60, 0.41, -0.92, 0.25, -1.0, 0.06)
    c.close_path()

def draw_fish(c, cx, cy, size, ang, flap, freeze=0.0, t=0.0):
    c.save(); c.translate(cx, cy); c.rotate(ang); c.scale(size / 2, size / 2)
    body_top = mix(hx('5f7f97'), hx('cfe9fa'), freeze)
    body_mid = mix(hx('aebfcc'), hx('e4f3fd'), freeze)
    body_bot = mix(hx('f4f6f6'), hx('f4fbff'), freeze)
    fin_c = mix(hx('8796a3'), hx('bfe0f5'), freeze)
    # tail (behind body)
    c.save(); c.translate(0.84, 0); c.rotate(flap * 0.45)
    c.move_to(0.0, -0.08); c.curve_to(0.18, -0.16, 0.30, -0.36, 0.42, -0.46)
    c.curve_to(0.40, -0.20, 0.30, -0.05, 0.30, 0.0)
    c.curve_to(0.30, 0.05, 0.40, 0.20, 0.42, 0.46)
    c.curve_to(0.30, 0.36, 0.18, 0.16, 0.0, 0.08); c.close_path()
    lin(c, 0, -0.4, 0.42, 0.4, [(0, fin_c), (1, mix(fin_c, hx('5b6b78'), 0.4 * (1 - freeze)))]); c.fill_preserve()
    c.set_source_rgba(1, 1, 1, 0.25); c.set_line_width(0.008); c.stroke()
    c.restore()
    # dorsal fin: translucent membrane + fine spines
    c.move_to(-0.44, -0.47)
    pts = []
    for i in range(10):
        x = -0.44 + i * 0.105; hgt = 0.17 * math.sin(math.pi * (i + 0.5) / 10.5) + 0.02 * math.sin(i * 1.7 + t * 6)
        pts.append((x, -0.47 + 0.16 * (i / 9) ** 2 - hgt))
    c.move_to(-0.44, -0.46)
    for (x, y) in pts: c.line_to(x, y)
    c.line_to(0.62, -0.30); c.close_path()
    lin(c, 0, -0.68, 0, -0.44, [(0, mix(hx('9aaab6', 0.55), hx('cfe9fa', 0.6), freeze)), (1, mix(hx('7d8f9c', 0.9), hx('bfe0f5', 0.9), freeze))]); c.fill()
    c.set_line_width(0.009)
    for i, (x, y) in enumerate(pts):
        c.move_to(x, -0.47 + 0.16 * (i / 9) ** 2 + 0.02); c.line_to(x, y)
        c.set_source_rgba(*mix(hx('5c6d7a'), hx('a9d3f0'), freeze)[:3], 0.8); c.stroke()
    # anal fin
    c.move_to(0.18, 0.40); c.line_to(0.30, 0.55 + 0.02 * math.sin(t * 7)); c.line_to(0.60, 0.40); c.line_to(0.66, 0.26); c.close_path()
    c.set_source_rgba(*fin_c[:3], 0.9); c.fill()
    # body
    fish_body(c)
    lin(c, 0, -0.5, 0, 0.45, [(0, body_top), (0.45, body_mid), (0.75, body_bot), (1, mix(hx('d8dde0'), hx('eaf6fd'), freeze))]); c.fill_preserve()
    c.save(); c.clip()
    # scale shimmer
    sh = (math.sin(t * 2.3) + 1) / 2
    lin(c, -1 + sh, -0.5, -0.2 + sh, 0.5, [(0, (1, 1, 1, 0)), (0.5, (1, 1, 1, 0.22)), (1, (1, 1, 1, 0))]); c.paint()
    # subtle longitudinal stripes (orata)
    c.set_line_width(0.012)
    for k in range(5):
        y = -0.32 + k * 0.08
        c.move_to(-0.55, y + 0.05); c.curve_to(-0.1, y - 0.03, 0.4, y + 0.02, 0.86, y * 0.25)
        c.set_source_rgba(*mix(hx('4f6a80'), hx('a8d4f0'), freeze)[:3], 0.14); c.stroke()
    # dark spot on gill (orata) + gill arc
    c.arc(-0.50, -0.14, 0.07, 0, 2 * math.pi); c.set_source_rgba(*mix(hx('3b4b58'), hx('9cc8e6'), freeze)[:3], 0.55); c.fill()
    c.move_to(-0.55, -0.32); c.curve_to(-0.42, -0.15, -0.42, 0.12, -0.56, 0.30)
    c.set_source_rgba(*mix(hx('6d7f8c'), hx('b4dbf3'), freeze)[:3], 0.8); c.set_line_width(0.018); c.stroke()
    c.restore()
    fish_body(c); c.set_source_rgba(1, 1, 1, 0.35); c.set_line_width(0.012); c.stroke()
    # golden eyebrow band (orata!)
    c.move_to(-0.86, -0.22); c.curve_to(-0.80, -0.30, -0.70, -0.32, -0.62, -0.30)
    c.set_source_rgba(*mix(hx('e8b33a'), hx('d9eefb'), freeze)[:3], 0.95); c.set_line_width(0.035); c.set_line_cap(cairo.LINE_CAP_ROUND); c.stroke()
    # eye
    c.arc(-0.76, -0.16, 0.075, 0, 2 * math.pi); c.set_source_rgba(*mix(hx('f2e6c4'), hx('eaf6fd'), freeze)); c.fill()
    c.arc(-0.76, -0.16, 0.048, 0, 2 * math.pi); c.set_source_rgba(*mix(hx('101820'), hx('5f8fb0'), freeze)); c.fill()
    c.arc(-0.775, -0.178, 0.016, 0, 2 * math.pi); c.set_source_rgba(1, 1, 1, 0.95); c.fill()
    # mouth
    c.move_to(-0.99, 0.05); c.curve_to(-0.94, 0.08, -0.90, 0.07, -0.87, 0.04)
    c.set_source_rgba(0.25, 0.3, 0.35, 0.7 * (1 - freeze)); c.set_line_width(0.012); c.stroke()
    # pectoral fin
    c.save(); c.translate(-0.38, 0.06); c.rotate(0.5 + 0.15 * math.sin(t * 9) * (1 - freeze))
    c.move_to(0, 0); c.curve_to(0.08, -0.05, 0.22, -0.02, 0.28, 0.06); c.curve_to(0.18, 0.10, 0.06, 0.08, 0, 0)
    c.set_source_rgba(*mix(hx('c7b38a'), hx('cfe9fa'), freeze)[:3], 0.85); c.fill(); c.restore()
    c.restore()

def wave_y(x, base, A, lam, ph):
    return base + A * np.sin(2 * np.pi * x / lam + ph) + A * 0.45 * np.sin(2 * np.pi * x / (lam * 0.53) + ph * 1.7 + 1.3)

def draw_wave(c, base, A, lam, ph, col_top, col_bot, crest=0.0):
    xs = np.linspace(-20, W + 20, 260)
    ys = wave_y(xs, base, A, lam, ph)
    c.move_to(xs[0], H + 10)
    for x, y in zip(xs, ys): c.line_to(x, y)
    c.line_to(xs[-1], H + 10); c.close_path()
    lin(c, 0, base - A, 0, H, [(0, col_top), (1, col_bot)]); c.fill()
    if crest > 0:
        c.move_to(xs[0], ys[0])
        for x, y in zip(xs, ys): c.line_to(x, y)
        c.set_source_rgba(1, 1, 1, crest); c.set_line_width(5); c.stroke()

class Drops:
    """simple ballistic droplets"""
    def __init__(self, seed, milk=False):
        self.r = np.random.default_rng(seed); self.p = []; self.milk = milk
    def burst(self, t0, x, y, n, vx=(-600, 600), vy=(-1700, -500), size=(6, 20)):
        for _ in range(n):
            self.p.append((t0, x + self.r.uniform(-60, 60), y, self.r.uniform(*vx), self.r.uniform(*vy), self.r.uniform(*size)))
    def draw(self, c, t, g=3200, floor=None, alpha=1.0):
        for (t0, x, y, vx, vy, s) in self.p:
            dt = t - t0
            if dt < 0 or dt > 1.6: continue
            px = x + vx * dt; py = y + vy * dt + 0.5 * g * dt * dt
            if floor is not None and py > floor and vy + g * dt > 0: continue
            a = alpha * clamp(1 - dt / 1.6)
            sp = math.hypot(vx, vy + g * dt)
            c.save(); c.translate(px, py); c.rotate(math.atan2(vy + g * dt, vx) - math.pi / 2)
            c.scale(1, 1 + min(1.8, sp / 1400))
            c.arc(0, 0, s, 0, 2 * math.pi)
            if self.milk: rad(c, -s * 0.3, -s * 0.3, 0, s * 1.2, [(0, (1, 1, 1, a)), (0.6, (1, 0.98, 0.93, a)), (1, (0.92, 0.86, 0.76, a * 0.9))])
            else: rad(c, -s * 0.3, -s * 0.3, 0, s * 1.2, [(0, (1, 1, 1, a)), (0.6, (0.85, 0.94, 1, a * 0.85)), (1, (0.6, 0.8, 0.95, a * 0.6))])
            c.fill(); c.restore()

FISH_DROPS = Drops(5)
FISH_DROPS.burst(1.42, 1920, 1255, 90, vx=(-1100, 1100), vy=(-2000, -600), size=(4, 12))
FISH_DROPS.burst(1.5, 1920, 1255, 60, vx=(-700, 700), vy=(-1200, -300), size=(3, 9))
for k in range(9): FISH_DROPS.burst(2.0 + k * 0.17, 1920 + rng0.uniform(-60, 60), 1330, 2, vx=(-60, 60), vy=(0, 150), size=(5, 10))

SNOW = [(rng0.random() * W, rng0.random() * H, rng0.uniform(2, 7), rng0.uniform(30, 120), rng0.random() * 6) for _ in range(160)]

def fish_sea(t):
    s, c = new_surface()
    # sky
    lin(c, 0, 0, 0, 1250, [(0, hx('081a28')), (0.55, hx('12344d')), (1, hx('3a7aa6'))]); c.paint()
    rad(c, 2900, 1150, 0, 1500, [(0, (1, 0.93, 0.8, 0.30)), (0.4, (0.6, 0.8, 1, 0.12)), (1, (0, 0, 0, 0))]); c.paint()
    # stars
    rr = np.random.default_rng(9)
    for _ in range(90):
        x, y = rr.random() * W, rr.random() * 800; tw = 0.5 + 0.5 * math.sin(t * rr.uniform(1, 3) + rr.random() * 6)
        c.arc(x, y, rr.uniform(1.5, 3.5), 0, 2 * math.pi); c.set_source_rgba(1, 1, 1, 0.25 + 0.4 * tw); c.fill()
    # far waves
    draw_wave(c, 1180, 10, 900, t * 0.9, hx('2a6f9e'), hx('0d3150'))
    draw_wave(c, 1215, 16, 1300, t * 1.2 + 1, hx('1f5f8c'), hx('0b2a45'), crest=0.10)
    # moon/sun reflection streaks
    for k in range(14):
        y = 1230 + k * 26; w_ = 420 * (1 - k / 16) * (0.7 + 0.3 * math.sin(t * 3 + k))
        c.move_to(2900 - w_ / 2, y); c.line_to(2900 + w_ / 2, y)
        c.set_source_rgba(1, 0.95, 0.85, 0.20 * (1 - k / 14)); c.set_line_width(6); c.stroke()
    return s, c

def fish_scene(t):
    s, c = fish_sea(t)
    # --- line + fish
    hook_y = lerp(-200, 1350, e_io3(prog(t, 0.2, 1.0)))
    rise = e_o3(prog(t, 1.25, 0.75))
    fy = lerp(1600, 720, rise)
    dang = clamp((t - 2.0) / 0.4)
    sway = math.sin(t * 2.2) * 30 * (1 - prog(t, 3.0, 0.8))
    fx = 1920 + sway
    freeze = e_io3(prog(t, 3.0, 1.0))
    flap = math.sin(t * 15) * (1 - freeze) * (0.4 + 0.6 * clamp((t - 1.25) / 0.3)) * (1 - 0.6 * dang * 0)
    ang = math.pi / 2 - 0.55 + math.sin(t * 5.5) * 0.12 * (1 - freeze) - 0.10 * (1 - rise)
    if t < 1.25:
        c.move_to(1920, -10); c.line_to(1920, hook_y)
        c.set_source_rgba(1, 1, 1, 0.75); c.set_line_width(4); c.stroke()
        # hook
        c.save(); c.translate(1920, hook_y); c.move_to(0, 0); c.line_to(0, 40); c.arc_negative(-16, 40, 16, 0, math.pi * 0.95)
        c.set_source_rgba(0.85, 0.88, 0.9, 1); c.set_line_width(6); c.stroke(); c.restore()
    else:
        L_ = 400
        mx_ = fx - math.cos(ang) * L_; my_ = fy - math.sin(ang) * L_
        c.move_to(1920 + sway * 0.2, -10); c.line_to(mx_, my_)
        c.set_source_rgba(1, 1, 1, 0.75 * (1 - prog(t, 4.0, 0.3))); c.set_line_width(4); c.stroke()
        draw_fish(c, fx, fy, 800, ang, flap, freeze, t)
    # front waves (occlude the fish while it is underwater)
    draw_wave(c, 1260, 22, 1100, t * 1.6 + 2, hx('17578a', 0.96), hx('082236'), crest=0.18)
    draw_wave(c, 1340, 30, 1500, t * 2.0 + 4, hx('0f4673', 0.98), hx('061a2a'), crest=0.15)
    # splash ring
    sp = prog(t, 1.4, 0.9)
    if 0 < sp < 1:
        for k in range(3):
            r = 120 + 520 * e_o3(sp) * (0.6 + 0.2 * k)
            c.save(); c.translate(1920, 1262); c.scale(1, 0.12); c.arc(0, 0, r, 0, 2 * math.pi); c.restore()
            c.set_source_rgba(1, 1, 1, 0.55 * (1 - sp) * (1 - 0.25 * k)); c.set_line_width(7); c.stroke()
    FISH_DROPS.draw(c, t, floor=1290)
    img = surf_rgba(s)[..., :3].copy()
    # ice block around fish
    if t >= 3.3:
        blk = e_o5(prog(t, 3.3, 0.9))
        ice_block(img, fx + 30, fy, blk, t, w=700, h=1060, rot=ang - math.pi / 2)
    # frost sparkles while freezing
    if 3.0 < t < 4.6:
        rr = np.random.default_rng(int(t * 25))
        for _ in range(int(40 * (1 - abs(t - 3.7) / 0.9))):
            add_glow(img, fx + rr.normal(0, 200), fy + rr.normal(0, 320), 18, (1, 1, 1), 0.8)
    return img

def ice_block_draw(c, cx, cy, k, w, h, rot=0.0, alpha=1.0, seed=4):
    """3D ice slab on cairo context, centred (cx,cy), rotated rot radians"""
    sc = lerp(0.82, 1.0, k); a = k * alpha
    if a <= 0: return
    c.save(); c.translate(cx, cy); c.rotate(rot); c.scale(sc, sc)
    d = min(w, h) * 0.09
    c.move_to(w / 2, -h / 2); c.line_to(w / 2 + d, -h / 2 - d * 0.6); c.line_to(w / 2 + d, h / 2 - d * 0.6); c.line_to(w / 2, h / 2); c.close_path()
    lin(c, w / 2, 0, w / 2 + d, 0, [(0, (0.62, 0.82, 0.95, 0.60 * a)), (1, (0.45, 0.68, 0.88, 0.50 * a))]); c.fill()
    c.move_to(-w / 2, -h / 2); c.line_to(-w / 2 + d, -h / 2 - d * 0.6); c.line_to(w / 2 + d, -h / 2 - d * 0.6); c.line_to(w / 2, -h / 2); c.close_path()
    c.set_source_rgba(0.88, 0.96, 1, 0.70 * a); c.fill()
    rr_ = max(10, min(w, h) * 0.035)
    rrect(c, -w / 2, -h / 2, w, h, rr_)
    lin(c, -w / 2, -h / 2, w / 2, h / 2, [(0, (0.80, 0.93, 1, 0.40 * a)), (0.5, (0.62, 0.84, 0.97, 0.26 * a)), (1, (0.75, 0.90, 1, 0.44 * a))]); c.fill_preserve()
    c.save(); c.clip()
    pat = cairo.SurfacePattern(AS.frost_pat); m = cairo.Matrix(); m.scale(1.6, 1.6); m.translate(w / 2 + 300, h / 2 + 200); pat.set_matrix(m)
    pat.set_extend(cairo.EXTEND_REPEAT)
    c.set_source(pat); c.paint_with_alpha(0.55 * a)
    # inner glow at edges
    for i in range(3):
        rrect(c, -w / 2 + 6 + i * 10, -h / 2 + 6 + i * 10, w - 12 - i * 20, h - 12 - i * 20, rr_)
        c.set_source_rgba(1, 1, 1, 0.12 * a); c.set_line_width(10); c.stroke()
    c.restore()
    rrect(c, -w / 2, -h / 2, w, h, rr_)
    c.set_source_rgba(1, 1, 1, 0.9 * a); c.set_line_width(max(3, w * 0.007)); c.stroke()
    c.move_to(-w / 2 + w * 0.06, -h / 2 + h * 0.06); c.line_to(-w / 2 + w * 0.06, h / 2 - h * 0.2)
    c.set_source_rgba(1, 1, 1, 0.6 * a); c.set_line_width(max(4, w * 0.018)); c.set_line_cap(cairo.LINE_CAP_ROUND); c.stroke()
    c.move_to(-w / 2 + w * 0.11, -h / 2 + h * 0.06); c.line_to(-w / 2 + w * 0.11, -h / 2 + h * 0.3)
    c.set_source_rgba(1, 1, 1, 0.38 * a); c.set_line_width(max(2, w * 0.009)); c.stroke()
    rr = np.random.default_rng(seed); c.set_line_width(max(1.5, w * 0.004))
    for _ in range(6):
        x, y = rr.uniform(-w / 2, w / 2) * 0.8, rr.uniform(-h / 2, h / 2) * 0.8; c.move_to(x, y)
        for _ in range(4): x += rr.uniform(-w, w) * 0.1; y += rr.uniform(-h, h) * 0.08; c.line_to(x, y)
        c.set_source_rgba(1, 1, 1, 0.35 * a); c.stroke()
    c.restore()

def ice_block(img, cx, cy, k, t, w=760, h=1180, rot=0.0):
    s, c = new_surface(); ice_block_draw(c, cx, cy, k, w, h, rot); over(img, surf_rgba(s))

def frost_wipe(img, p):
    """frost growing over whole frame (p 0..1..), white-ice"""
    if p <= 0: return
    fb = AS.frost_big
    yy = (np.arange(H, dtype=np.float32)[:, None] - H / 2) / (H / 2); xx = (np.arange(W, dtype=np.float32)[None, :] - W / 2) / (W / 2)
    rmap = np.sqrt(xx * xx * 0.6 + yy * yy * 0.9)
    edge = (1.4 - p * 1.6)  # radius threshold shrinks -> frost from edges to centre
    m = np.clip((rmap - edge) / 0.25 + fb * 0.6 - 0.2, 0, 1)
    m = np.clip(m + max(0, p - 0.8) * 5, 0, 1)
    col = np.array([0.90, 0.96, 1.0], np.float32)
    tex = np.clip(0.86 + 0.20 * fb, 0, 1)[..., None] * col
    img *= 1 - m[..., None]; img += tex * m[..., None]

# ---------------------------------------------------- store scene: chest freezer
FZ = dict(x0=900, x1=2940, top=1180, front_h=760, depth=300, inset=90)
def store_bg(c, t):
    lin(c, 0, 0, 0, H, [(0, hx('0a1d2a')), (0.62, hx('15364d')), (0.63, hx('1c4561')), (1, hx('0b2232'))]); c.paint()
    for (x, a) in [(1100, .16), (1920, .22), (2740, .16)]:
        c.move_to(x - 60, -10); c.line_to(x + 60, -10); c.line_to(x + 520, 1400); c.line_to(x - 520, 1400); c.close_path()
        lin(c, 0, 0, 0, 1400, [(0, (0.75, 0.9, 1, a)), (1, (0.75, 0.9, 1, 0))]); c.fill()
    rad(c, 1920, 1350, 0, 1700, [(0, (0.45, 0.72, 0.95, 0.20)), (1, (0, 0, 0, 0))]); c.paint()

def freezer_back(c, lid_open, inner_glow):
    f = FZ; x0, x1, top, dp, ins = f['x0'], f['x1'], f['top'], f['depth'], f['inset']
    # top rim (perspective trapezoid)
    c.move_to(x0, top); c.line_to(x0 + ins, top - dp); c.line_to(x1 - ins, top - dp); c.line_to(x1, top); c.close_path()
    lin(c, 0, top - dp, 0, top, [(0, hx('d9e3ea')), (1, hx('f6f9fb'))]); c.fill()
    # well
    m = 46
    c.move_to(x0 + m, top - 14); c.line_to(x0 + ins + m * 0.7, top - dp + 18); c.line_to(x1 - ins - m * 0.7, top - dp + 18); c.line_to(x1 - m, top - 14); c.close_path()
    lin(c, 0, top - dp, 0, top, [(0, hx('0b3150')), (1, hx('1d6aa0'))]); c.fill_preserve()
    c.save(); c.clip()
    rad(c, 1920, top - dp / 2, 0, 900, [(0, (0.7, 0.9, 1, 0.45 * inner_glow)), (1, (0, 0, 0, 0))]); c.paint()
    c.restore()

def freezer_front(c, lid_open, t):
    f = FZ; x0, x1, top, dp, ins, fh = f['x0'], f['x1'], f['top'], f['depth'], f['inset'], f['front_h']
    m = 46
    yf, yb = top - 14, top - dp + 18
    xf0, xf1 = x0 + m, x1 - m
    kb = ((x1 - ins - m * 0.7) - 1920) / (xf1 - 1920)
    def P(x, back): return 1920 + (x - 1920) * (kb if back else 1.0)
    half = (xf1 - xf0) / 2
    panels = [(xf0 + lid_open * half * 0.97, xf0 + half + lid_open * half * 0.97), (xf0 + half, xf1)]
    for k_, (a0, a1) in enumerate(panels[::-1]):
        c.move_to(P(a0, 0), yf); c.line_to(P(a0, 1), yb); c.line_to(P(a1, 1), yb); c.line_to(P(a1, 0), yf); c.close_path()
        lin(c, P(a0, 1), yb, P(a1, 0), yf, [(0, (0.82, 0.94, 1, 0.30)), (0.5, (0.66, 0.86, 1, 0.16)), (1, (0.86, 0.96, 1, 0.34))]); c.fill_preserve()
        c.set_source_rgba(0.93, 0.97, 1, 0.95); c.set_line_width(9); c.stroke()
        # handle groove + reflection
        c.move_to(P(a0 + 40, 0), yf - 6); c.line_to(P(a0 + 40, 1), yb + 6); c.set_source_rgba(0.8, 0.86, 0.9, 0.9); c.set_line_width(10); c.stroke()
        c.move_to(P(a0 + half * 0.35, 0), yf - 4); c.line_to(P(a0 + half * 0.55, 1), yb + 4)
        c.set_source_rgba(1, 1, 1, 0.30); c.set_line_width(40); c.stroke()
    # front body
    rrect(c, x0, top, x1 - x0, fh, 30)
    lin(c, 0, top, 0, top + fh, [(0, hx('ffffff')), (0.55, hx('e9eff4')), (1, hx('c9d5de'))]); c.fill()
    # brand band
    c.rectangle(x0, top + 60, x1 - x0, 120); lin(c, x0, 0, x1, 0, [(0, hx('1f6fb5')), (0.5, hx('2f86c8')), (1, hx('1f6fb5'))]); c.fill()
    c.rectangle(x0, top + 180, x1 - x0, 10); c.set_source_rgba(*hx('e3232c')); c.fill()
    # grille
    for k in range(6):
        c.move_to(x0 + 260, top + fh - 150 + k * 16); c.line_to(x1 - 260, top + fh - 150 + k * 16)
        c.set_source_rgba(0.55, 0.62, 0.68, 0.6); c.set_line_width(5); c.stroke()
    # floor shadow
    c.save(); c.translate(1920, top + fh + 10); c.scale(1, 0.08); c.arc(0, 0, (x1 - x0) * 0.6, 0, 2 * math.pi); c.restore()
    rad(c, 1920, top + fh + 10, 0, (x1 - x0) * 0.6, [(0, (0, 0, 0, 0.5)), (1, (0, 0, 0, 0))]); c.fill()

def fish_store(t, tl):
    """tl: local time in store part (0 at frost clear)"""
    s, c = new_surface()
    store_bg(c, tl)
    lid = e_io3(prog(tl, 0.0, 0.45)) * (1 - e_io3(prog(tl, 1.35, 0.45)))
    freezer_back(c, lid, 0.6 + 0.4 * lid)
    img = surf_rgba(s)[..., :3].copy()
    # falling block: tilts from vertical to lying flat, lands inside the well
    fall = prog(tl, 0.15, 0.8)
    land_y = FZ['top'] - 30
    by = lerp(-500, land_y, e_i2(fall))
    if tl > 0.95: by = land_y + 14 * math.sin((tl - 0.95) * 22) * math.exp(-(tl - 0.95) * 9)
    rot = lerp(math.pi / 2 * 0.0 + 0.9, 0.0, e_o3(fall))
    s2, c2 = new_surface()
    c2.save(); c2.translate(1920, by); c2.rotate(rot)
    draw_fish(c2, 0, 0, 470, 0.0, 0, 1.0, t)
    c2.restore()
    ice_block_draw(c2, 1920, by, 1.0, 600, 300, rot)
    over(img, surf_rgba(s2))
    # front of freezer on top
    s3, c3 = new_surface()
    freezer_front(c3, lid, tl)
    over(img, surf_rgba(s3))
    # logo on front
    lg = AS.logo_sf_navy
    blit(img, lg, 1920, FZ['top'] + 470, 1.0, 0.24)
    # cold mist puff when block lands
    mp = prog(tl, 0.9, 2.4)
    if 0 < mp < 1:
        rr = np.random.default_rng(11)
        for k in range(26):
            ang = rr.uniform(-math.pi, 0); spd = rr.uniform(200, 900)
            x = 1920 + math.cos(ang) * spd * e_o3(mp) * 1.3 + rr.normal(0, 200)
            y = FZ['top'] - 160 + math.sin(ang) * spd * e_o3(mp) * 0.5 - 200 * mp
            add_glow(img, x, y, int(rr.uniform(110, 220)), (0.92, 0.97, 1), 0.22 * (1 - mp) * clamp(mp * 8))
    # title
    tp = e_o5(prog(tl, 1.5, 0.9))
    if tp > 0:
        blit(img, AS.t_fish1, 1920, 330 + (1 - tp) * 40, tp)
        tp2 = e_o5(prog(tl, 1.7, 0.9))
        blit(img, AS.t_fish2, 1920, 520 + (1 - tp2) * 50, tp2)
        tp3 = e_o5(prog(tl, 1.95, 0.9))
        blit(img, AS.t_fish3, 1920, 700 + (1 - tp3) * 50, tp3)
    # snow
    for (x, y, r, sp, ph) in SNOW:
        yy = (y + sp * t) % H; xx = x + 20 * math.sin(t + ph)
        add_glow(img, xx, yy, int(r * 3), (1, 1, 1), 0.35)
    return img

def render_fish(t):
    assets()
    if not hasattr(AS, 't_fish1'):
        AS.t_fish1 = text_layer('DAL MARE AL TUO FREEZER', 66, 600, (169, 211, 240, 255), 18)
        AS.t_fish2 = text_layer('PESCATO', 210, 800, (255, 255, 255, 255), 6)
        AS.t_fish3 = text_layer('CONGELATO', 150, 800, (159, 208, 242, 255), 10)
    T_SW = 4.35
    if t < T_SW + 0.35:
        img = fish_scene(min(t, T_SW + 0.35))
        frost_wipe(img, prog(t, 3.9, 0.8))
    else:
        img = fish_store(t, t - (T_SW + 0.35))
        p = 1 - prog(t, T_SW + 0.35, 0.45)
        if p > 0: frost_wipe(img, 0.8 + 0.2 * p if p > 0.05 else p)
    return np.clip(img, 0, 1)

VIGS = dict(fish=render_fish)
def render_vig(name, t): return VIGS[name](t)

# ================================================================== CORNETTO
CUP = dict(cx=2350, top=1160, rx=330, ry=88, bot=1560, brx=215)
def croissant(c, wet=0.0, t=0.0):
    """croissant in local coords: horns at x=-1 / +1, curving downward (crescent)."""
    def axis(u): return (u * 1.0, 0.55 * (u * u) - 0.16)
    BND = [-0.95, -0.74, -0.50, -0.20, 0.20, 0.50, 0.74, 0.95]
    def scal(u):
        for i in range(len(BND) - 1):
            if BND[i] <= u <= BND[i + 1]:
                f = (u - BND[i]) / (BND[i + 1] - BND[i]); return 1 + 0.13 * math.sin(math.pi * f) ** 0.8
        return 1.0
    def width(u): return (0.40 * max(0.0, 1 - u * u) ** 0.7 + 0.03) * scal(u)
    us = np.linspace(-1, 1, 301)
    def edge(u, side):
        x, y = axis(u); x2, y2 = axis(u + 1e-3); dx, dy = x2 - x, y2 - y; L = math.hypot(dx, dy)
        nx, ny = -dy / L, dx / L
        w_ = width(u) * (1.0 if side < 0 else 0.82)
        return x + nx * w_ * side, y + ny * w_ * side
    def outline():
        p = [edge(u, -1) for u in us] + [edge(u, 1) for u in us[::-1]]
        c.move_to(*p[0])
        for q in p[1:]: c.line_to(*q)
        c.close_path()
    # base fill + shadow side
    outline()
    lin(c, 0, -0.55, 0, 0.45, [(0, hx('f2b462')), (0.45, hx('d9832f')), (1, hx('8c4514'))]); c.fill_preserve()
    c.save(); c.clip()
    # rolled bands: boundaries curving toward the centre
    bounds = BND
    for i in range(len(bounds) - 1):
        u0, u1 = bounds[i], bounds[i + 1]
        um = (u0 + u1) / 2
        bulge = 0.09 * (1 if um < 0 else -1) * (0 if abs(um) < 0.05 else 1)
        # band polygon
        pts = []
        for v in np.linspace(-1, 1, 24):   # across width
            x0, y0 = axis(u0); x1_, y1_ = axis(u1)
            pass
        c.new_path()
        top0, top1 = edge(u0, -1.15), edge(u1, -1.15); bot0, bot1 = edge(u0, 1.2), edge(u1, 1.2)
        mid0 = axis(u0); mid1 = axis(u1)
        c.move_to(*top0)
        c.curve_to(mid0[0] + bulge * 1.5, mid0[1] - 0.1, mid0[0] + bulge * 1.5, mid0[1] + 0.1, *bot0)
        c.line_to(*bot1)
        c.curve_to(mid1[0] - bulge * 1.5, mid1[1] + 0.1, mid1[0] - bulge * 1.5, mid1[1] - 0.1, *top1)
        c.close_path()
        cx_, cy_ = axis(um)
        tone = 1.0 - 0.28 * abs(um) ** 1.3
        g = cairo.RadialGradient(cx_ - 0.05, cy_ - width(um) * 0.55, 0.01, cx_, cy_, width(um) * 1.6 + 0.12)
        for o, col in [(0, (1.0 * tone, 0.80 * tone, 0.46 * tone, 1)), (0.45, (0.90 * tone, 0.55 * tone, 0.22 * tone, 1)),
                       (1, (0.55 * tone, 0.27 * tone, 0.08 * tone, 1))]:
            g.add_color_stop_rgba(o, *col)
        c.set_source(g); c.fill_preserve()
        c.set_source_rgba(0.42, 0.19, 0.05, 0.75); c.set_line_width(0.016); c.stroke()
        # flaky texture lines inside band
        c.set_line_width(0.005)
        for k in range(3):
            f = (k + 1) / 4; uu = u0 + (u1 - u0) * f
            p1, p2 = edge(uu, -0.85), edge(uu, 0.9); m_ = axis(uu)
            c.move_to(*p1); c.curve_to(m_[0] + bulge, m_[1] - 0.05, m_[0] + bulge, m_[1] + 0.05, *p2)
            c.set_source_rgba(0.55, 0.28, 0.08, 0.30); c.stroke()
    # top gloss along the back
    c.new_path()
    for j, u in enumerate(np.linspace(-0.7, 0.7, 40)):
        x, y = edge(u, -0.55)
        (c.move_to if j == 0 else c.line_to)(x, y)
    c.set_source_rgba(1, 0.95, 0.8, 0.45); c.set_line_width(0.05); c.set_line_cap(cairo.LINE_CAP_ROUND); c.stroke()
    # milk coating on dunked left horn
    if wet > 0:
        c.new_path(); x, y = axis(-1.0)
        g = cairo.RadialGradient(x - 0.05, y + 0.05, 0.0, x, y, 0.55)
        g.add_color_stop_rgba(0, 1, 0.98, 0.92, 0.55 * wet); g.add_color_stop_rgba(0.6, 1, 0.97, 0.9, 0.28 * wet); g.add_color_stop_rgba(1, 1, 0.97, 0.9, 0)
        c.set_source(g); c.paint()
    c.restore()
    outline(); c.set_source_rgba(0.40, 0.18, 0.05, 0.6); c.set_line_width(0.012); c.stroke()

def cup_back(c):
    p = CUP
    # saucer
    c.save(); c.translate(p['cx'], p['bot'] + 10); c.scale(1, 0.2); c.arc(0, 0, 560, 0, 2 * math.pi); c.restore()
    rad(c, p['cx'], p['bot'] + 40, 0, 600, [(0, (0, 0, 0, 0.25)), (1, (0, 0, 0, 0))]); c.fill()
    c.save(); c.translate(p['cx'], p['bot']); c.scale(1, 0.2); c.arc(0, 0, 520, 0, 2 * math.pi); c.restore()
    lin(c, p['cx'] - 520, 0, p['cx'] + 520, 0, [(0, hx('ffffff')), (0.6, hx('eef1f4')), (1, hx('c9d2da'))]); c.fill_preserve()
    c.set_source_rgba(*hx('2f86c8')); c.set_line_width(7); c.stroke()
    c.save(); c.translate(p['cx'], p['bot'] - 6); c.scale(1, 0.2); c.arc(0, 0, 330, 0, 2 * math.pi); c.restore()
    c.set_source_rgba(0.80, 0.85, 0.9, 0.6); c.fill()
    # handle (right)
    c.save(); c.translate(p['cx'] + p['rx'] - 30, p['top'] + 170)
    c.move_to(0, -90); c.curve_to(190, -140, 230, 110, 10, 150); c.line_to(0, 100); c.curve_to(150, 80, 130, -70, 0, -40); c.close_path()
    lin(c, 0, -100, 220, 100, [(0, hx('ffffff')), (1, hx('c3cdd6'))]); c.fill(); c.restore()
    # body
    c.move_to(p['cx'] - p['rx'], p['top'])
    c.curve_to(p['cx'] - p['rx'], p['top'] + 260, p['cx'] - p['brx'] - 40, p['bot'] - 40, p['cx'] - p['brx'], p['bot'])
    c.curve_to(p['cx'] - 80, p['bot'] + 28, p['cx'] + 80, p['bot'] + 28, p['cx'] + p['brx'], p['bot'])
    c.curve_to(p['cx'] + p['brx'] + 40, p['bot'] - 40, p['cx'] + p['rx'], p['top'] + 260, p['cx'] + p['rx'], p['top'])
    c.close_path()
    lin(c, p['cx'] - p['rx'], 0, p['cx'] + p['rx'], 0, [(0, hx('dfe5ea')), (0.25, hx('ffffff')), (0.7, hx('eef2f5')), (1, hx('b8c3cd'))]); c.fill()
    # inner wall (back half ellipse) + milk
    c.save(); c.translate(p['cx'], p['top']); c.scale(p['rx'], p['ry']); c.arc(0, 0, 1, 0, 2 * math.pi); c.restore()
    lin(c, 0, p['top'] - p['ry'], 0, p['top'] + p['ry'], [(0, hx('c8d1d9')), (1, hx('f4f6f8'))]); c.fill()

def milk_surface(c, ripple_t, drips):
    p = CUP; my = p['top'] + 26; mrx, mry = p['rx'] - 26, p['ry'] - 12
    c.save(); c.translate(p['cx'], my); c.scale(mrx, mry); c.arc(0, 0, 1, 0, 2 * math.pi); c.restore()
    rad(c, p['cx'] - 60, my - 20, 0, mrx, [(0, hx('fffdf8')), (0.7, hx('f6efe2')), (1, hx('e6dccb'))]); c.fill()
    c.save(); c.translate(p['cx'], my); c.scale(mrx, mry); c.arc(0, 0, 1, 0, 2 * math.pi); c.restore(); c.save(); c.clip()
    for (t0, x0) in ripple_t:
        for k in range(3):
            r = (ripple_t and 1) * 0
    c.restore()
    return my, mrx, mry

def cup_rim(c):
    p = CUP
    # front rim highlight (lower half of the top ellipse)
    c.save(); c.translate(p['cx'], p['top']); c.scale(p['rx'], p['ry']); c.arc(0, 0, 1, 0, math.pi); c.restore()
    c.set_source_rgba(1, 1, 1, 1); c.set_line_width(14); c.stroke()
    c.save(); c.translate(p['cx'], p['top']); c.scale(p['rx'], p['ry']); c.arc(0, 0, 1, 0, 2 * math.pi); c.restore()
    c.set_source_rgba(*hx('2f86c8')); c.set_line_width(6); c.stroke()

CORN_DROPS = Drops(21, milk=True)
CORN_DROPS.burst(1.95, CUP['cx'] - 40, CUP['top'] + 20, 46, vx=(-700, 700), vy=(-1500, -500), size=(5, 13))
for k in range(8): CORN_DROPS.burst(3.15 + k * 0.16, 0, 0, 1, vx=(-20, 20), vy=(0, 60), size=(7, 12))

def cornetto_pose(t):
    p = CUP
    tip_dunk = (p['cx'] - 40, p['top'] + 150)
    s1 = e_io3(prog(t, 0.5, 1.3)); s2 = e_io3(prog(t, 1.8, 0.35)); s3 = e_io3(prog(t, 2.9, 0.9)); s4 = e_io3(prog(t, 3.8, 1.2))
    ang = lerp(-0.2, -0.95, s1) + lerp(0, 0.75, s3) + 0.06 * math.sin(t * 2)
    size = 900
    # tip in local coords is at (-1, 0.28) (left horn end); place so tip goes to target
    tx, ty = lerp(3300, tip_dunk[0] - 20, s1), lerp(-300, tip_dunk[1] - 230, s1)
    ty += 230 * s2 - 300 * s3 - 220 * s4
    tx += 320 * s3 + 120 * s4
    bob = 10 * math.sin((t - 2.2) * 12) * math.exp(-max(0, t - 2.2) * 6) if t > 2.2 else 0
    return tx, ty + bob, ang, size

def render_cornetto(t):
    assets()
    if not hasattr(AS, 't_c1'):
        AS.t_c1 = text_layer('PASTICCERIA CONGELATA', 66, 700, (226, 106, 150, 255), 14)
        AS.t_c2 = text_layer('LA COLAZIONE', 200, 900, (22, 50, 74, 255), 4)
        AS.t_c3 = text_layer('È SERVITA!', 200, 900, (47, 134, 200, 255), 4)
    s, c = new_surface()
    lin(c, 0, 0, 0, H, [(0, hx('fdf3e7')), (0.62, hx('f3dcc4')), (0.63, hx('ead2bb')), (1, hx('d9b99a'))]); c.paint()
    rad(c, 2400, 700, 0, 1900, [(0, (1, 1, 1, 0.65)), (1, (1, 1, 1, 0))]); c.paint()
    rr = np.random.default_rng(31)
    for _ in range(14):
        x, y, r = rr.uniform(0, W), rr.uniform(0, 1200), rr.uniform(60, 200)
        c.arc(x + 15 * math.sin(t * 0.4 + x), y, r, 0, 2 * math.pi); rad(c, x, y, 0, r, [(0, (1, 0.95, 0.85, 0.22)), (1, (1, 0.95, 0.85, 0))]); c.fill()
    # table edge
    c.rectangle(0, 1340, W, 8); c.set_source_rgba(1, 1, 1, 0.35); c.fill()
    cup_back(c)
    my, mrx, mry = milk_surface(c, [], [])
    # ripples on milk
    c.save(); c.translate(CUP['cx'], my); c.scale(mrx, mry); c.arc(0, 0, 1, 0, 2 * math.pi); c.restore(); c.save(); c.clip()
    for (t0, x0, amp) in [(1.98, -40, 1.0), (2.15, -40, 0.6), (3.2, -40, 0.35), (3.6, -40, 0.3), (4.0, -40, 0.25)]:
        dt = t - t0
        if 0 < dt < 1.6:
            for k in range(2):
                r = 30 + (dt - k * 0.15) * 260
                if r <= 0: continue
                c.save(); c.translate(CUP['cx'] + x0, my + 4); c.scale(1, mry / mrx); c.arc(0, 0, r, 0, 2 * math.pi); c.restore()
                c.set_source_rgba(0.80, 0.72, 0.60, 0.45 * amp * (1 - dt / 1.6)); c.set_line_width(6); c.stroke()
    c.restore()
    # croissant (clip away the part under the milk while dunked)
    tx, ty, ang, size = cornetto_pose(t)
    wet = clamp((t - 2.0) / 0.3)
    c.save()
    # clip: everything except milk volume (ellipse + below)
    c.rectangle(0, 0, W, H)
    c.move_to(CUP['cx'] - mrx, my)
    c.save(); c.translate(CUP['cx'], my); c.scale(mrx, mry); c.arc(0, 0, 1, math.pi, 2 * math.pi); c.restore()
    c.line_to(CUP['cx'] + mrx, H); c.line_to(CUP['cx'] - mrx, H); c.close_path()
    c.set_fill_rule(cairo.FILL_RULE_EVEN_ODD); c.clip(); c.set_fill_rule(cairo.FILL_RULE_WINDING)
    c.translate(tx, ty); c.rotate(ang); c.scale(size / 2, size / 2); c.translate(1.0, -0.30)
    croissant(c, wet, t)
    c.restore()
    cup_rim(c)
    # drops: splash crown + drips from tip
    CORN_DROPS.draw(c, t, floor=my + 10)
    tipx, tipy = tx, ty
    for k in range(8):
        t0 = 3.15 + k * 0.16; dt = t - t0
        if 0 < dt < 0.8:
            sx, sy = cornetto_pose(t0)[:2]
            py = sy + 30 + 0.5 * 3000 * dt * dt
            if py < my:
                c.save(); c.translate(sx - 10, py); c.scale(1, 1.5); c.arc(0, 0, 11, 0, 2 * math.pi); c.restore()
                c.set_source_rgba(1, 0.98, 0.93, 0.95); c.fill()
    img = surf_rgba(s)[..., :3].copy()
    # steam (blurred strokes)
    s2, c2 = new_surface(W // 4, H // 4)
    c2.scale(0.25, 0.25)
    for k in range(3):
        c2.move_to(CUP['cx'] - 120 + k * 120, my - 40)
        for j in range(1, 12):
            y = my - 40 - j * 70; x = CUP['cx'] - 120 + k * 120 + 50 * math.sin(j * 0.7 + t * 2.2 + k * 2)
            c2.line_to(x, y)
        c2.set_source_rgba(1, 1, 1, 0.55 * (1 - prog(t, 1.6, 0.5)) + 0.25); c2.set_line_width(46); c2.set_line_cap(cairo.LINE_CAP_ROUND); c2.stroke()
    st = surf_rgba(s2); st = cv2.GaussianBlur(st, (0, 0), 9); st = cv2.resize(st, (W, H), interpolation=cv2.INTER_LINEAR)
    over(img, st, 0.6)
    # title
    tp = e_o5(prog(t, 4.0, 0.9)); x_ = 1000
    if tp > 0:
        blit(img, AS.t_c1, x_, 640 + (1 - tp) * 40, tp)
        tp2 = e_o5(prog(t, 4.2, 0.9)); blit(img, AS.t_c2, x_, 860 + (1 - tp2) * 60, tp2)
        tp3 = e_o5(prog(t, 4.4, 0.9)); blit(img, AS.t_c3, x_, 1080 + (1 - tp3) * 60, tp3)
    return np.clip(img, 0, 1)

VIGS['cornetto'] = render_cornetto


# ================================================================== FREEZER DOOR
FD = dict(x0=2050, x1=3330, y0=180, y1=1990)
def load_cut(x, h):
    a = load_rgba(S + f'/cut/x{x}.png'); s_ = h / a.shape[0]
    return np.clip(cv2.resize(a, (int(a.shape[1] * s_), int(h)), interpolation=cv2.INTER_AREA if s_ < 1 else cv2.INTER_CUBIC), 0, 1)

def render_freezer(t):
    assets()
    if not hasattr(AS, 'fz_prod'):
        AS.fz_prod = [[load_cut(226, 400), load_cut(223, 400)], [load_cut(39, 420), load_cut(36, 300)], [load_cut(220, 300), load_cut(42, 300)]]
        AS.t_f1 = text_layer('SCOPRI LE OFFERTE', 66, 700, (169, 211, 240, 255), 16)
        AS.t_f2 = text_layer('GRANDI', 220, 900, (255, 255, 255, 255), 4)
        AS.t_f3 = text_layer('MARCHE', 220, 900, (76, 201, 196, 255), 4)
        AS.t_f4 = text_layer('SURGELATE', 110, 800, (255, 255, 255, 255), 12)
        AS.logo_sf_small = cv2.resize(AS.logo_sf_white, (int(AS.logo_sf_white.shape[1] * 0.16), int(AS.logo_sf_white.shape[0] * 0.16)), interpolation=cv2.INTER_AREA)
    f = FD; x0, x1, y0, y1 = f['x0'], f['x1'], f['y0'], f['y1']
    s, c = new_surface()
    # store aisle background
    lin(c, 0, 0, 0, H, [(0, hx('0a1d2a')), (0.70, hx('16374e')), (0.71, hx('1d4560')), (1, hx('0a2030'))]); c.paint()
    rad(c, (x0 + x1) / 2, 900, 0, 2200, [(0, (0.5, 0.78, 1, 0.22)), (1, (0, 0, 0, 0))]); c.paint()
    # neighbour freezers (dim) for depth
    rrect(c, x1 + 260, y0 + 140, 900, y1 - y0 - 140, 30); c.set_source_rgba(0.6, 0.75, 0.9, 0.05); c.fill()
    c.save(); c.translate((x0 + x1) / 2, y1 + 60); c.scale(1, 0.06); c.arc(0, 0, 900, 0, 2 * math.pi); c.restore()
    rad(c, (x0 + x1) / 2, y1 + 60, 0, 900, [(0, (0, 0, 0, 0.55)), (1, (0, 0, 0, 0))]); c.fill()
    # cabinet body
    rrect(c, x0 - 40, y0 - 40, x1 - x0 + 80, y1 - y0 + 80, 40)
    lin(c, x0, 0, x1, 0, [(0, hx('9aa7b3')), (0.5, hx('e8eef3')), (1, hx('8b98a4'))]); c.fill()
    # header band with logo
    c.rectangle(x0, y0, x1 - x0, 210); lin(c, 0, y0, 0, y0 + 210, [(0, hx('2f86c8')), (1, hx('1f6fb5'))]); c.fill()
    c.rectangle(x0, y0 + 210, x1 - x0, 10); c.set_source_rgba(*hx('e3232c')); c.fill()
    # interior
    iy0 = y0 + 240
    light = clamp((t - 0.6) / 0.25) * (0.85 + 0.15 * (1 if t > 1.0 else (0.5 + 0.5 * math.sin(t * 60))))
    c.rectangle(x0 + 20, iy0, x1 - x0 - 40, y1 - iy0 - 20)
    lin(c, 0, iy0, 0, y1, [(0, mix(hx('20384a'), hx('eaf6ff'), light)), (1, mix(hx('0f2232'), hx('a9cfee'), light))]); c.fill()
    c.rectangle(x0 + 40, iy0 + 10, x1 - x0 - 80, 18); c.set_source_rgba(1, 1, 1, 0.3 + 0.7 * light); c.fill()
    shelves = [iy0 + 500, iy0 + 1010, iy0 + 1520]
    for sy in shelves:
        c.rectangle(x0 + 30, sy, x1 - x0 - 60, 22); lin(c, 0, sy, 0, sy + 22, [(0, hx('f4f7fa')), (1, hx('9aa7b3'))]); c.fill()
        c.rectangle(x0 + 30, sy + 22, x1 - x0 - 60, 30); c.set_source_rgba(0, 0, 0, 0.18); c.fill()
    img = surf_rgba(s)[..., :3].copy()
    # products on shelves (pop forward after door opens)
    for r_, row in enumerate(AS.fz_prod):
        for k, prod in enumerate(row):
            pop = e_oback(prog(t, 2.2 + 0.18 * (r_ * 2 + k), 0.6), 1.6)
            sc = 0.92 + 0.10 * pop
            cx = x0 + (x1 - x0) * (0.33 + 0.41 * k); cy = shelves[r_] - prod.shape[0] * sc / 2 - 4
            blit(img, prod, cx, cy, 0.35 + 0.65 * light, sc)
    # door (hinged on the left, swings open toward viewer)
    op = e_io3(prog(t, 1.1, 1.1))
    s2, c2 = new_surface()
    dx0, dx1 = x0 + 10, x1 - 10; dy0, dy1 = iy0 - 10, y1 - 10
    ang = op * 1.25
    wproj = (dx1 - dx0) * math.cos(ang); grow = 1 + 0.18 * math.sin(ang)
    rx = dx0 - wproj if False else dx0 + wproj
    rx = dx0 - (dx1 - dx0) * 0.0
    xr = dx0 + (dx1 - dx0) * math.cos(ang) - 260 * math.sin(ang)
    hy = (dy1 - dy0) * (grow - 1) / 2
    c2.move_to(dx0, dy0); c2.line_to(xr, dy0 - hy); c2.line_to(xr, dy1 + hy); c2.line_to(dx0, dy1); c2.close_path()
    lin(c2, dx0, 0, xr, 0, [(0, (0.80, 0.92, 1, 0.30)), (0.5, (0.65, 0.84, 1, 0.20)), (1, (0.85, 0.95, 1, 0.38))]); c2.fill_preserve()
    c2.save(); c2.clip()
    pat = cairo.SurfacePattern(AS.frost_pat); m = cairo.Matrix(); m.scale(1.1, 1.1); pat.set_matrix(m); pat.set_extend(cairo.EXTEND_REPEAT)
    c2.set_source(pat); c2.paint_with_alpha(0.75 * (1 - 0.65 * op) * (1 - 0.5 * prog(t, 0.0, 0.9)))
    c2.move_to(dx0 + 200, dy0); c2.line_to(dx0 + 700, dy1); c2.set_source_rgba(1, 1, 1, 0.18); c2.set_line_width(120); c2.stroke()
    c2.restore()
    c2.move_to(dx0, dy0); c2.line_to(xr, dy0 - hy); c2.line_to(xr, dy1 + hy); c2.line_to(dx0, dy1); c2.close_path()
    c2.set_source_rgba(0.85, 0.9, 0.95, 1); c2.set_line_width(26); c2.stroke()
    # handle
    hx_ = xr - 70 * (1 - op * 0.5)
    c2.move_to(hx_, (dy0 + dy1) / 2 - 380 * grow); c2.line_to(hx_, (dy0 + dy1) / 2 + 380 * grow)
    c2.set_source_rgba(0.75, 0.8, 0.86, 1); c2.set_line_width(30); c2.set_line_cap(cairo.LINE_CAP_ROUND); c2.stroke()
    over(img, surf_rgba(s2))
    blit(img, AS.logo_sf_small, (x0 + x1) / 2, y0 + 105, 1.0)
    # cold mist pouring out (after opening)
    mp = prog(t, 1.4, 6.0)
    if mp > 0:
        rr = np.random.default_rng(17)
        for k in range(70):
            t0 = rr.uniform(0, 3.5); dt = t - 1.4 - t0
            if dt < 0: continue
            life = 2.4; q = dt / life
            if q > 1: continue
            x = x0 + rr.uniform(50, x1 - x0 - 50) + rr.uniform(-1, 1) * 600 * q
            y = rr.uniform(iy0 + 200, y1 - 300) + 900 * q * q
            y = min(y, y1 + 40 - 30 * q)
            add_glow(img, x, y, int(rr.uniform(140, 280)), (0.92, 0.97, 1), 0.30 * math.sin(math.pi * q))
    # floor reflection & sparkle
    for k in range(18):
        rr = np.random.default_rng(100 + k); tt_ = (t * 0.7 + rr.random()) % 1
        if light > 0.5 and op > 0.5: add_glow(img, x0 + rr.uniform(100, x1 - x0 - 100), iy0 + rr.uniform(100, 1700), 16, (1, 1, 1), 0.8 * math.sin(math.pi * tt_))
    # titles (left)
    tx = 1000
    for i, (lay, y, d) in enumerate([(AS.t_f1, 640, 2.6), (AS.t_f2, 870, 2.75), (AS.t_f3, 1110, 2.9), (AS.t_f4, 1320, 3.05)]):
        p = e_o5(prog(t, d, 0.9))
        if p > 0: blit(img, lay, tx, y + (1 - p) * 60, p)
    return np.clip(img, 0, 1)

VIGS['freezer'] = render_freezer

if __name__ == '__main__':
    name = sys.argv[1]; os.makedirs(S + '/testv', exist_ok=True)
    for tt in sys.argv[2:]:
        im = render_vig(name, float(tt))
        Image.fromarray((np.clip(im, 0, 1) * 255 + .5).astype(np.uint8)).save(f'{S}/testv/{name}_{float(tt):05.2f}.png')
