#!/usr/bin/env python3
"""Superfreddo 4K flyer video renderer.  usage: render.py frame <t> <out.png> | chunk <i> <n> <out.mp4>"""
import os, sys, math, subprocess, glob
import numpy as np, cv2, pymupdf
from PIL import Image, ImageDraw, ImageFont

cv2.setNumThreads(1)
S = os.path.dirname(os.path.abspath(__file__))
A = S + '/assets'
PDF = '/root/.claude/uploads/f3a91526-5260-545e-8804-83615d42bc0d/a7027054-volantino_super_freddo.pdf'
UP = '/root/.claude/uploads/f3a91526-5260-545e-8804-83615d42bc0d'
W, H, FPS = 3840, 2160, 25
BAR = 2.0  # 120 BPM, 4/4
SHUT = 0.5 / 25  # 180 degree shutter

def hexc(h):
    h = h.lstrip('#'); return np.array([int(h[i:i+2], 16) / 255 for i in (0, 2, 4)], np.float32)

ICE = hexc('a9d3f0'); WHITE = hexc('ffffff'); RED = hexc('e3232c'); NAVY = hexc('1a3545')

# ---------------------------------------------------------------- easing
def clamp(x, a=0., b=1.): return a if x < a else b if x > b else x
def lerp(a, b, t): return a + (b - a) * t
def prog(t, t0, d): return clamp((t - t0) / d)
def e_io3(x): return 4*x*x*x if x < .5 else 1 - (-2*x + 2)**3 / 2
def e_io4(x): return 8*x**4 if x < .5 else 1 - (-2*x + 2)**4 / 2
def e_o3(x): return 1 - (1 - x)**3
def e_o5(x): return 1 - (1 - x)**5
def e_i3(x): return x**3
def e_oback(x, s=1.2): x -= 1; return 1 + (s + 1) * x**3 + s * x**2

# ---------------------------------------------------------------- sprites
class Sprite:
    """premultiplied float32 RGBA with sqrt2 mip chain; drawn with subpixel affine."""
    def __init__(self, rgba):
        rgba = rgba.astype(np.float32)
        if rgba.max() > 1.5: rgba /= 255.
        rgba[..., :3] *= rgba[..., 3:4]
        self.levels = [rgba]; f = 1.0
        while min(self.levels[-1].shape[:2]) > 48:
            f /= math.sqrt(2)
            h0, w0 = rgba.shape[:2]
            self.levels.append(cv2.resize(rgba, (max(1, round(w0*f)), max(1, round(h0*f))), interpolation=cv2.INTER_AREA))
        self.h, self.w = rgba.shape[:2]

    def draw(self, cv, cx, cy, scale, alpha=1.0, sx=None, tint=None, mb=None):
        if alpha <= 0.002 or scale <= 0: return
        sy = scale; sx = scale if sx is None else sx
        dw, dh = self.w * sx, self.h * sy
        x0, y0 = cx - dw/2, cy - dh/2
        BL = 0.0
        if mb is not None:
            BL = math.hypot(mb[0], mb[1])
            if BL < 1.5: BL = 0.0
        ex = int(abs(mb[0]) / 2 + 3) if BL else 2; ey = int(abs(mb[1]) / 2 + 3) if BL else 2
        X0, Y0 = max(0, int(math.floor(x0)) - ex), max(0, int(math.floor(y0)) - ey)
        X1, Y1 = min(cv.shape[1], int(math.ceil(x0 + dw)) + ex), min(cv.shape[0], int(math.ceil(y0 + dh)) + ey)
        if X1 <= X0 or Y1 <= Y0: return
        m = min(sx, sy); L = 0
        while L + 1 < len(self.levels) and m <= (1/math.sqrt(2))**(L+1) * 1.0001: L += 1
        lv = self.levels[L]; lh, lw = lv.shape[:2]
        kx, ky = dw / lw, dh / lh
        M = np.array([[kx, 0, x0 - X0 + 0.5*kx - 0.5], [0, ky, y0 - Y0 + 0.5*ky - 0.5]], np.float32)
        interp = cv2.INTER_CUBIC if max(kx, ky) > 1.01 else cv2.INTER_LINEAR
        src = cv2.warpAffine(lv, M, (X1 - X0, Y1 - Y0), flags=interp, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
        if interp == cv2.INTER_CUBIC: np.clip(src, 0, 1, out=src)
        if BL:
            k = int(math.ceil(BL)) | 1
            ker = np.zeros((k, k), np.float32)
            c = k // 2; ux, uy = mb[0] / BL, mb[1] / BL
            for j in range(4 * k):
                f = j / (4 * k - 1) - 0.5
                ker[int(round(c + uy * f * (k - 1))), int(round(c + ux * f * (k - 1)))] += 1
            ker /= ker.sum()
            src = cv2.filter2D(src, -1, ker, borderType=cv2.BORDER_CONSTANT)
        if tint is not None: src[..., :3] = tint * src[..., 3:4]
        roi = cv[Y0:Y1, X0:X1]
        a = src[..., 3:4] * alpha
        roi *= (1 - a); roi += src[..., :3] * alpha
        return (X0, Y0, X1, Y1)

def rounded_mask(w, h, r, ss=4):
    m = Image.new('L', (w*ss, h*ss), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, w*ss - 1, h*ss - 1], r*ss, fill=255)
    return np.asarray(m.resize((w, h), Image.LANCZOS), np.float32) / 255

def shadow_sprite(w, h, r, blur, pad=None):
    """soft shadow for a w x h rounded rect, returned as Sprite of size (w+2pad, h+2pad), downsampled 4x for speed"""
    pad = pad or int(blur * 2.2)
    q = 4
    sw, sh = (w + 2*pad) // q, (h + 2*pad) // q
    m = np.zeros((sh, sw), np.float32)
    cv2.rectangle(m, (pad//q, pad//q), ((pad + w)//q, (pad + h)//q), 1.0, -1)
    m = cv2.GaussianBlur(m, (0, 0), blur / q)
    rgba = np.zeros((sh, sw, 4), np.float32); rgba[..., 3] = m
    sp = Sprite(rgba); sp.q = q; sp.pad = pad
    return sp

FONT = {w: S + f'/fonts/Jost-{w}.ttf' for w in (400, 500, 600, 700, 800, 900)}
def text_sprite(txt, size, weight=700, color=(255, 255, 255), track=0):
    f = ImageFont.truetype(FONT[weight], size)
    # manual tracking
    widths = [f.getlength(c) for c in txt]
    tw = int(sum(widths) + track * (len(txt) - 1)) + 8
    asc, desc = f.getmetrics()
    im = Image.new('RGBA', (tw, asc + desc + 8), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    x = 4
    for c, wd in zip(txt, widths):
        d.text((x, 4), c, font=f, fill=color + (255,)); x += wd + track
    a = np.asarray(im, np.float32)
    bb = im.getbbox()
    sp = Sprite(a[:, :bb[2] + 2])
    sp.ink_top, sp.ink_bot = bb[1], bb[3]
    return sp

def load_png_sprite(p): return Sprite(np.asarray(Image.open(p).convert('RGBA'), np.float32))

# ---------------------------------------------------------------- pdf assets
DOC = pymupdf.open(PDF)
PW, PH = DOC[0].rect.width, DOC[0].rect.height
def render_clip(pn, rect, zoom):
    pix = DOC[pn].get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=pymupdf.Rect(*rect), alpha=False)
    rgb = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, 3).astype(np.float32) / 255
    return rgb

# ---------------------------------------------------------------- layout
PAGE_H = 1830; PAGE_W = PAGE_H * PW / PH
PAGE_X = 250; PAGE_Y = 95
PAGE_CX, PAGE_CY = PAGE_X + PAGE_W/2, PAGE_Y + PAGE_H/2
PANEL_X = 1720
BOX_CX, BOX_CY, BOX_W, BOX_H = 2700, 1265, 1880, 1300
FOOT_Y = 2010

# per-page content -------------------------------------------------------
G = hexc('d4ab55'); O = hexc('f7ab1d'); P = hexc('f5a8bf'); T = hexc('4cc9c4'); I2 = hexc('9fd0f2'); R2 = hexc('ff4a4f')
PAGES = [
    dict(label='PAGINA 1 DI 8', l1='VOLANTINO', l2='SUPERFREDDO', c=I2,
         cards=[(45, 372, 555, 772)]),
    dict(label='PAGINA 2 DI 8', l1='PRODOTTI ANNIVERSARIO', l2='PESCATO CONGELATO', c=G,
         cards=[(6, 92, 590, 270), (10, 338, 300, 500), (12, 501, 299, 770), (300, 553, 577, 673)]),
    dict(label='PAGINA 3 DI 8', l1='SFIZIOSITÀ', l2='CONGELATE', c=O,
         cards=[(298, 0, 584, 505), (12, 502, 299, 770), (10, 70, 282, 292), (300, 512, 577, 650)]),
    dict(label='PAGINA 4 DI 8', l1='SFIZIOSITÀ', l2='CONGELATE', c=O,
         cards=[(298, 0, 584, 505), (12, 502, 299, 770), (10, 68, 282, 290), (300, 512, 577, 650)]),
    dict(label='PAGINA 5 DI 8', l1='PRIMI E SFIZIOSITÀ', l2='CONGELATE', c=O,
         cards=[(298, 0, 584, 505), (12, 502, 299, 770), (10, 68, 282, 290), (10, 290, 282, 495)]),
    dict(label='PAGINA 6 DI 8', l1='PASTICCERIA', l2='CONGELATA', c=P,
         cards=[(298, 0, 584, 358), (12, 502, 299, 770), (10, 56, 292, 212), (300, 512, 577, 648)]),
    dict(label='PAGINA 7 DI 8', l1='CONFEZIONATI', l2='GRANDI MARCHE', c=T,
         cards=[(298, 0, 584, 366), (10, 502, 585, 794), (10, 70, 292, 212), (296, 366, 584, 500)]),
    dict(label='PAGINA 8 DI 8', l1='SUPER CONCORSO', l2='20 ANNI DECÒ', c=R2,
         cards=[(0, 0, 595.3, 262), (0, 268, 595.3, 500), (22, 512, 575, 768)],
         mark=(2, (312, 699.5, 582, 712.5))),
]

# ---------------------------------------------------------------- timeline (seconds)
INTRO = 8.0
def page_dur(i): return 8.0 if i == 0 else 2.0 + 4.0 * len(PAGES[i]['cards'])
SPOT1 = dict(file=UP + '/628b850d-anziani.mp4', dur=36.0, key='anz')
SPOT2 = dict(file=UP + '/a01acf43-WhatsApp_Video_2026-10-09_at_19.06.13.mp4', dur=46.0, key='card')
OUTRO = 10.0
SEQ = []  # (kind, start, dur, payload)
t = 0.0
SEQ.append(('intro', t, INTRO, None)); t += INTRO
def add_block(pages):
    global t
    start = t; sched = []
    for p in pages: sched.append((p, t - start)); t += page_dur(p)
    SEQ.append(('pages', start, t - start, sched))
add_block([0, 1, 2, 3])
SEQ.append(('spot', t, SPOT1['dur'], SPOT1)); t += SPOT1['dur']
add_block([4, 5, 6])
SEQ.append(('spot', t, SPOT2['dur'], SPOT2)); t += SPOT2['dur']
add_block([7])
SEQ.append(('outro', t, OUTRO, None)); t += OUTRO
TOTAL = t
WIPE = 0.9  # wipe duration centred on each scene boundary

# ---------------------------------------------------------------- background
rng = np.random.default_rng(7)
def build_bg():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    u = (xx / W * 0.55 + yy / H * 0.45)
    top, bot = hexc('0b1f2c'), hexc('1c4560')
    bg = top[None, None] * (1 - u[..., None]) + bot[None, None] * u[..., None]
    # soft glows baked
    for (gx, gy, r, c, a) in [(3300, 250, 1700, hexc('5fb0e0'), .22), (500, 2100, 1500, hexc('2f7fb0'), .18), (1900, 1000, 2300, hexc('15384d'), .25)]:
        d = np.exp(-((xx - gx)**2 + (yy - gy)**2) / (2 * (r/2)**2))[..., None]
        bg = bg * (1 - a*d) + c * a * d
    # frost: multi-octave noise, very subtle
    n = np.zeros((H, W), np.float32)
    for oct_, amp in [(16, .5), (48, .3), (160, .2)]:
        small = rng.random((H // oct_ + 2, W // oct_ + 2)).astype(np.float32)
        n += amp * cv2.resize(small, (W, H), interpolation=cv2.INTER_CUBIC)[:H, :W]
    n = (n - n.mean()) / n.std()
    bg += (n * 0.010)[..., None] * np.array([.8, .9, 1.0], np.float32)
    # vignette
    v = ((xx - W/2) / (W*.62))**2 + ((yy - H/2) / (H*.72))**2
    bg *= (1 - 0.38 * np.clip(v, 0, 1.6)[..., None] / 1.6)
    # fine dither grain to avoid banding on LED walls
    bg += (rng.random((H, W, 1), np.float32) - .5) / 255 * 1.2
    return np.clip(bg, 0, 1).astype(np.float32)

def blob(r, hard=False):
    s = int(r * 2 + 8) | 1
    yy, xx = np.mgrid[0:s, 0:s].astype(np.float32); c = s / 2
    d = np.sqrt((xx - c)**2 + (yy - c)**2)
    if hard: a = np.clip(r - d + .5, 0, 1) * 0.85 + np.clip(1 - d / (r*2.2 + 1e-3), 0, 1)**2 * .15
    else: a = np.exp(-(d / (r * .62))**2) * (1 - np.clip((d - r) / 3, 0, 1))
    rgba = np.zeros((s, s, 4), np.float32); rgba[..., :3] = 1; rgba[..., 3] = a
    return Sprite(rgba)

class Particles:
    def __init__(self):
        self.p = []
        for i in range(110):
            z = rng.random() ** 1.6
            r = lerp(2.2, 7, z) if rng.random() < .7 else lerp(14, 60, z)
            big = r > 12
            self.p.append(dict(x=rng.random() * W, y=rng.random() * H, r=r, big=big,
                               vx=lerp(4, 22, z) * (1 if rng.random() < .6 else -1), vy=lerp(10, 55, z),
                               a=(lerp(.035, .09, rng.random()) if big else lerp(.25, .6, rng.random()) * lerp(.6, 1, z)),
                               ph=rng.random() * 6.28, sw=lerp(8, 40, rng.random()), fr=lerp(.1, .3, rng.random())))
        self.sprites = {}
    def sp(self, r, big):
        k = (round(r * 2) / 2, big)
        if k not in self.sprites: self.sprites[k] = blob(k[0], hard=not big)
        return self.sprites[k]
    def draw(self, cv, t, alpha=1.0):
        for q in self.p:
            x = (q['x'] + q['vx'] * t + q['sw'] * math.sin(q['ph'] + t * q['fr'] * 6.28)) % (W + 200) - 100
            y = (q['y'] + q['vy'] * t) % (H + 200) - 100
            self.sp(q['r'], q['big']).draw(cv, x, y, 1.0, q['a'] * alpha, tint=hexc('e8f6ff'))

# ---------------------------------------------------------------- globals built lazily
class Assets: pass
AS = Assets()
def build_cards(i):
    pg = PAGES[i]; lst = []
    for r in pg['cards']:
        rw, rh = r[2] - r[0], r[3] - r[1]
        fit = min(BOX_W / rw, BOX_H / rh)
        hold_w, hold_h = rw * fit, rh * fit
        zoom = fit * 1.08
        rgb = render_clip(i, r, zoom)
        h0, w0 = rgb.shape[:2]
        m = rounded_mask(w0, h0, 26 * zoom / fit)
        sp = Sprite(np.dstack([rgb, m])); sp.hold = fit / zoom
        sp.fit = fit; sp.rect = r
        lst.append((sp, shadow_sprite(int(hold_w), int(hold_h), 0, 45)))
    return lst

class LazyCards:
    def __init__(self): self.c = {}
    def __getitem__(self, i):
        if i not in self.c:
            if len(self.c) >= 2: self.c.pop(next(iter(self.c)))
            self.c[i] = build_cards(i)
        return self.c[i]

def setup():
    AS.bg = build_bg()
    AS.parts = Particles()
    AS.logo_deco20 = load_png_sprite(A + '/logo_deco20.png')
    AS.logo_sf = load_png_sprite(A + '/logo_superfreddo.png')
    # pages
    z = PAGE_H / PH * 1.42
    AS.pages = []; AS.page_shadow = shadow_sprite(int(PAGE_W), int(PAGE_H), 0, 55)
    for i in range(8):
        rgb = render_clip(i, (0, 0, PW, PH), z)
        rgba = np.dstack([rgb, np.ones(rgb.shape[:2], np.float32)])
        sp = Sprite(rgba); sp.base_scale = PAGE_W / rgba.shape[1]
        AS.pages.append(sp)
    AS.cards = LazyCards()
    # titles
    AS.titles = []
    for pg in PAGES:
        lab = text_sprite(pg['label'], 50, 600, (169, 211, 240), track=9)
        def fit_text(s, col):
            size = 150
            while True:
                sp = text_sprite(s, size, 800, col, track=2)
                if sp.w <= 1950 or size < 70: return sp
                size -= 4
        c = tuple(int(v * 255) for v in pg['c'])
        l1 = fit_text(pg['l1'], c); l2 = fit_text(pg['l2'], (255, 255, 255))
        AS.titles.append((lab, l1, l2))
    # footer
    AS.foot_date = text_sprite('OFFERTE VALIDE DAL 13 AL 22 OTTOBRE 2026', 50, 600, (255, 255, 255), track=5)
    AS.foot_store = text_sprite('COLLEFERRO  ·  VIA DEI PIOPPI, 24', 46, 600, (169, 211, 240), track=4)
    # intro / outro text
    AS.t_date = text_sprite('OFFERTE VALIDE DAL 13 AL 22 OTTOBRE 2026', 78, 700, (255, 255, 255), track=6)
    AS.t_wait = text_sprite('TI ASPETTIAMO A', 64, 600, (169, 211, 240), track=14)
    AS.t_city = text_sprite('COLLEFERRO', 190, 800, (255, 255, 255), track=6)
    AS.t_addr = text_sprite('VIA DEI PIOPPI, 24', 92, 600, (255, 255, 255), track=8)
    AS.t_app = text_sprite("SCARICA L'APP DECÒ", 54, 700, (255, 255, 255), track=6)
    AS.t_vol = text_sprite('IL NUOVO VOLANTINO', 70, 600, (169, 211, 240), track=22)
    # QR block from back page (vector, scannable)
    qr = render_clip(7, (424, 404, 580, 494), 9.5)
    AS.qr = Sprite(np.dstack([qr, rounded_mask(qr.shape[1], qr.shape[0], 40)]))
    AS.qr_sh = shadow_sprite(qr.shape[1], qr.shape[0], 0, 40)
    AS.spots = {}

def pill_sprite(w, h, col):
    m = rounded_mask(w, h, h // 2)
    rgba = np.zeros((h, w, 4), np.float32); rgba[..., :3] = col; rgba[..., 3] = m
    return Sprite(rgba)

def draw_shadow(cv, sh, cx, cy, scale, alpha, dy=30, mb=None):
    sh.draw(cv, cx, cy + dy * scale, scale * sh.q, alpha, tint=np.zeros(3, np.float32), mb=mb)

def draw_bg(cv, t, alpha=1.0):
    cv[:] = AS.bg
    AS.parts.draw(cv, t, alpha)

def draw_footer(cv, t, a):
    if a <= 0: return
    y0 = FOOT_Y
    band = cv[y0:H]
    band *= 1 - 0.55 * a
    band += hexc('071721') * 0.55 * a
    # hairline
    line = cv[y0:y0 + 3]
    line *= 1 - .7 * a; line += ICE * .7 * a
    cy = (y0 + H) / 2 + 2
    sf = AS.logo_sf
    sc = 0.125
    sf.draw(cv, PAGE_X + sf.w * sc / 2, cy, sc, a)
    x = PAGE_X + sf.w * sc + 90
    cv[int(cy - 40):int(cy + 40), int(x - 45):int(x - 42)] = cv[int(cy - 40):int(cy + 40), int(x - 45):int(x - 42)] * (1 - .5 * a) + ICE * .5 * a
    AS.foot_date.draw(cv, x + AS.foot_date.w / 2, cy, 1, a)
    AS.foot_store.draw(cv, W - 250 - AS.foot_store.w / 2, cy, 1, a)

def shine(cv, rect, p, strength=.32):
    """diagonal light sweep across rect (x0,y0,x1,y1) at progress p 0..1"""
    if p <= 0 or p >= 1: return
    x0, y0, x1, y1 = [int(round(v)) for v in rect]
    x0, y0 = max(0, x0), max(0, y0); x1, y1 = min(W, x1), min(H, y1)
    if x1 <= x0 or y1 <= y0: return
    hh, ww = y1 - y0, x1 - x0
    yy, xx = np.mgrid[0:hh, 0:ww].astype(np.float32)
    pos = lerp(-0.35 * (ww + hh), 1.35 * (ww + hh), e_io3(p))
    d = (xx + yy * 0.6) - pos
    band = np.exp(-(d / (0.09 * (ww + hh)))**2) * strength
    roi = cv[y0:y1, x0:x1]
    roi += (1 - roi) * band[..., None]

# ---------------------------------------------------------------- page scene
def page_tf(t_rel, d, entering_first):
    """returns (cx, cy, scale_mult, alpha) for a page given time relative to its own start (t_rel) and its duration"""
    cx, cy, s, a = PAGE_CX, PAGE_CY, 1.0, 1.0
    # enter 0..1.1s from right
    if t_rel < 1.3:
        p = e_io3(prog(t_rel, 0, 1.3)) if not entering_first else e_o3(prog(t_rel, 0, 1.4))
        cx = lerp(W + PAGE_W * 0.6, PAGE_CX, p)
        s = lerp(0.95, 1.0, p)
    if t_rel > d:
        p = e_io3(prog(t_rel - d, 0, 1.3))
        cx = lerp(PAGE_CX, -PAGE_W * 0.62, p)
        s = lerp(1.0, 0.95, p)
    # slow breathing push-in
    s *= 1.0 + 0.012 * clamp(t_rel / max(d, 1))
    return cx, cy, s, a

def card_screen_rect(pi, r, pcx, pcy, ps):
    k = PAGE_H / PH * ps
    x0 = pcx - PAGE_W * ps / 2 + r[0] * k; y0 = pcy - PAGE_H * ps / 2 + r[1] * k
    return x0, y0, x0 + (r[2] - r[0]) * k, y0 + (r[3] - r[1]) * k

def draw_title(cv, pi, t_rel, d):
    lab, l1, l2 = AS.titles[pi]
    x = PANEL_X; ytop = 150
    def ln(sp, y, delay, out_delay):
        pin = e_o5(prog(t_rel, 1.0 + delay, 0.9))
        pout = e_i3(prog(t_rel, d + out_delay, 0.45))
        a = pin * (1 - pout)
        if a <= 0: return
        dy = (1 - pin) * 70 - pout * 50
        sp.draw(cv, x + sp.w / 2, y + sp.h / 2 + dy, 1.0, a)
    # red accent bar
    pin = e_o5(prog(t_rel, 0.95, 0.8)); pout = e_i3(prog(t_rel, d, 0.4))
    bw = 150 * pin * (1 - pout)
    if bw > 1:
        cv[ytop:ytop + 10, x:x + int(bw)] = RED
    ln(l1, ytop + 45, 0.08, 0.05)
    ln(l2, ytop + 45 + l1.ink_bot - 6, 0.16, 0.1)

def card_pose(pi, ci, t_c, pcx, pcy, ps, hold_len):
    sp, sh = AS.cards[pi][ci]
    r = sp.rect
    sx0, sy0, sx1, sy1 = card_screen_rect(pi, r, pcx, pcy, ps)
    fly = 0.85
    p = e_io4(prog(t_c, 0, fly))
    sc = math.exp(lerp(math.log((sx1 - sx0) / sp.w), math.log(sp.hold), p))
    cx = lerp((sx0 + sx1) / 2, BOX_CX, p); cy = lerp((sy0 + sy1) / 2, BOX_CY, p) - math.sin(p * math.pi) * 60
    return cx, cy

def draw_card(cv, pi, ci, t_c, pcx, pcy, ps, hold_len):
    """t_c: time since card start; card flies from page to box, holds, exits"""
    sp, sh = AS.cards[pi][ci]
    c1 = card_pose(pi, ci, t_c, pcx, pcy, ps, hold_len); c2 = card_pose(pi, ci, t_c + SHUT, pcx, pcy, ps, hold_len)
    mbv = (c2[0] - c1[0], c2[1] - c1[1])
    r = sp.rect
    sx0, sy0, sx1, sy1 = card_screen_rect(pi, r, pcx, pcy, ps)
    src_cx, src_cy = (sx0 + sx1) / 2, (sy0 + sy1) / 2
    src_scale = (sx1 - sx0) / sp.w
    hold_scale = sp.hold
    fly = 0.85
    p = e_io4(prog(t_c, 0, fly))
    # log-space scale interpolation looks like a natural camera zoom
    sc = math.exp(lerp(math.log(src_scale), math.log(hold_scale), p))
    cx = lerp(src_cx, BOX_CX, p); cy = lerp(src_cy, BOX_CY, p) - math.sin(p * math.pi) * 60
    # slow push during hold
    hp = prog(t_c, fly, hold_len)
    sc *= 1 + 0.035 * e_io3(hp) * p
    a = 1.0
    pout = e_i3(prog(t_c, fly + hold_len, 0.45))
    if pout > 0:
        sc *= lerp(1, 0.9, pout); a = 1 - pout; cy += 40 * pout
    # highlight + dim on page
    hl = e_o3(prog(t_c, 0, 0.5)) * (1 - e_o3(prog(t_c, fly + hold_len, 0.45)))
    if hl > 0:
        pass  # dim handled by caller before drawing card (needs page rect)
    # shadow
    sh_scale = sc / hold_scale
    sh.draw(cv, cx, cy + 34 * sh_scale, sh_scale * sh.q, 0.6 * a * clamp(p * 1.5), tint=np.zeros(3, np.float32), mb=mbv)
    box = sp.draw(cv, cx, cy, sc, a, mb=mbv)
    # shine after landing
    if box and a > .5:
        w_, h_ = sp.w * sc, sp.h * sc
        shine(cv, (cx - w_/2, cy - h_/2, cx + w_/2, cy + h_/2), prog(t_c, fly - 0.05, 1.0))
    return hl, (sx0, sy0, sx1, sy1), (cx, cy, sc, a)

def dim_page(cv, prect, hole, k):
    x0, y0, x1, y1 = [int(round(v)) for v in prect]
    x0, y0 = max(0, x0), max(0, y0); x1, y1 = min(W, x1), min(FOOT_Y, y1)
    if x1 <= x0 or y1 <= y0: return
    roi = cv[y0:y1, x0:x1]
    m = np.full(roi.shape[:2], 1 - 0.42 * k, np.float32)
    hx0, hy0, hx1, hy1 = [int(round(v)) for v in hole]
    hx0, hy0, hx1, hy1 = max(hx0, x0) - x0, max(hy0, y0) - y0, min(hx1, x1) - x0, min(hy1, y1) - y0
    if hx1 > hx0 and hy1 > hy0: m[hy0:hy1, hx0:hx1] = 1
    m = cv2.GaussianBlur(m, (0, 0), 3)
    roi *= m[..., None]
    roi += (hexc('0b1f2c') * 0.42 * k) * (1 - m[..., None]) / max(0.42 * k, 1e-6) * 0.42 * k * 0  # keep neutral
    # outline around hole
    if hx1 > hx0 and hy1 > hy0:
        col = ICE * (0.9 * k) + 0
        t_ = 6
        hx0a, hy0a, hx1a, hy1a = max(0, hx0 - t_), max(0, hy0 - t_), min(roi.shape[1], hx1 + t_), min(roi.shape[0], hy1 + t_)
        for (a0, a1, b0, b1) in [(hy0a, hy0, hx0a, hx1a), (hy1, hy1a, hx0a, hx1a), (hy0a, hy1a, hx0a, hx0), (hy0a, hy1a, hx1, hx1a)]:
            if a1 > a0 and b1 > b0:
                roi[a0:a1, b0:b1] = roi[a0:a1, b0:b1] * (1 - k) + col

def draw_pages_block(cv, tl, sched, block_dur):
    draw_bg(cv, tl + 0)
    # footer fades in at block start
    fa = e_o3(prog(tl, 0.2, 0.8))
    for idx, (pi, ps) in enumerate(sched):
        d = page_dur(pi)
        tr = tl - ps
        last = idx == len(sched) - 1
        if tr < 0: continue
        if not last and tr > d + 1.35: continue
        if last: tr_eff = min(tr, d)      # last page of block stays until wipe
        else: tr_eff = tr
        cx, cy, s, a = page_tf(tr_eff, d, idx == 0)
        cx2, cy2, _, _ = page_tf(tr_eff + SHUT, d, idx == 0)
        mbv = (cx2 - cx, cy2 - cy)
        sc = AS.pages[pi].base_scale * s
        draw_shadow(cv, AS.page_shadow, cx, cy, s, .65 * a, dy=26, mb=mbv)
        AS.pages[pi].draw(cv, cx, cy, sc, a, mb=mbv)
        prect = (cx - PAGE_W * s / 2, cy - PAGE_H * s / 2, cx + PAGE_W * s / 2, cy + PAGE_H * s / 2)
        if tr_eff <= d + 0.5:
            draw_title(cv, pi, tr_eff, d)
        # cards
        ncard = len(PAGES[pi]['cards'])
        for ci in range(ncard):
            if pi == 0: c0, hold = 2.0, 6.0 - 0.85 - 0.45
            else: c0, hold = 2.0 + 4.0 * ci, 4.0 - 0.85 - 0.45
            t_c = tr_eff - c0
            if t_c < 0 or t_c > 0.85 + hold + 0.45: continue
            r = PAGES[pi]['cards'][ci]
            hole = card_screen_rect(pi, r, cx, cy, s)
            hl = e_o3(prog(t_c, 0, 0.5)) * (1 - e_o3(prog(t_c, 0.85 + hold, 0.45)))
            dim_page(cv, prect, hole, hl)
            _, _, (ccx, ccy, csc, ca) = draw_card(cv, pi, ci, t_c, cx, cy, s, hold)
            mk = PAGES[pi].get('mark')
            if mk and mk[0] == ci:
                sp = AS.cards[pi][ci][0]
                mr = mk[1]; cr = sp.rect
                k = sp.fit * csc / sp.hold  # px per pt on screen
                mx0 = ccx - sp.w * csc / 2 + (mr[0] - cr[0]) * k; my0 = ccy - sp.h * csc / 2 + (mr[1] - cr[1]) * k
                mx1 = mx0 + (mr[2] - mr[0]) * k; my1 = my0 + (mr[3] - mr[1]) * k
                pa = e_o3(prog(t_c, 1.0, 0.5)) * ca
                if pa > 0:
                    pulse = 0.5 + 0.5 * math.sin((t_c - 1.0) * 2 * math.pi * 1.0)
                    g = 6 + 4 * pulse
                    draw_ring(cv, mx0 - 12, my0 - 9, mx1 + 12, my1 + 9, RED, pa, 9, 16 + 12 * pulse)
    draw_footer(cv, tl, fa)

def draw_ring(cv, x0, y0, x1, y1, col, a, thick, glow):
    X0, Y0, X1, Y1 = int(x0 - glow * 3), int(y0 - glow * 3), int(x1 + glow * 3), int(y1 + glow * 3)
    X0, Y0, X1, Y1 = max(0, X0), max(0, Y0), min(W, X1), min(H, Y1)
    if X1 <= X0 or Y1 <= Y0: return
    m = np.zeros((Y1 - Y0, X1 - X0), np.float32)
    ss = 4
    big = Image.new('L', ((X1 - X0) * ss, (Y1 - Y0) * ss), 0)
    ImageDraw.Draw(big).rounded_rectangle([(x0 - X0) * ss, (y0 - Y0) * ss, (x1 - X0) * ss, (y1 - Y0) * ss], 12 * ss, outline=255, width=int(thick * ss))
    m = np.asarray(big.resize((X1 - X0, Y1 - Y0), Image.LANCZOS), np.float32) / 255
    gl = cv2.GaussianBlur(m, (0, 0), glow) * 1.6
    tot = np.clip(m + gl * 0.6, 0, 1)[..., None] * a
    roi = cv[Y0:Y1, X0:X1]
    roi *= 1 - tot; roi += col * tot

# ---------------------------------------------------------------- intro / outro
def draw_intro(cv, tl):
    draw_bg(cv, tl)
    # global slow drift up of the lockup
    p1 = prog(tl, 0.3, 1.6); a1 = e_o3(p1)
    d20 = AS.logo_deco20; sf = AS.logo_sf
    lock_y = lerp(0, -170, e_io4(prog(tl, 4.0, 1.4)))
    s20 = 0.42 * lerp(0.86, 1.0, e_o5(p1))
    d20.draw(cv, W/2, 640 + lock_y + (1 - a1) * 40, s20, a1)
    # superfreddo: reveal by left->right soft wipe
    p2 = prog(tl, 1.2, 1.5)
    if p2 > 0:
        layer = np.zeros_like(cv[:, :, :1]).repeat(3, 2)
        tmp = np.zeros((H, W, 3), np.float32)
        ssf = 0.62 * lerp(0.97, 1.0, e_o3(p2))
        cy = 1240 + lock_y
        box = None
        # draw onto black temp to get premult color + alpha via two passes
        tmpa = np.zeros((H, W, 3), np.float32)
        sf.draw(tmp, W/2, cy, ssf, 1.0)
        sf.draw(tmpa, W/2, cy, ssf, 1.0, tint=np.ones(3, np.float32))
        wsf = sf.w * ssf
        x0 = W/2 - wsf/2 - 100
        edge = lerp(x0, x0 + wsf + 300, e_io3(p2))
        xs = np.arange(W, dtype=np.float32)
        mask = np.clip((edge - xs) / 160, 0, 1)[None, :, None]
        al = tmpa[..., :1] * mask
        cv *= 1 - al; cv += tmp * mask
    # light sweep over the lockup
    sp = prog(tl, 2.9, 1.3)
    if 0 < sp < 1:
        shine_mask_area(cv, (W/2 - 1000, 300 + lock_y, W/2 + 1000, 1560 + lock_y), sp)
    # subtitle line + date pill
    pv = e_o5(prog(tl, 4.4, 1.0))
    if pv > 0:
        AS.t_vol.draw(cv, W/2, 1560 + (1 - pv) * 50, 1, pv)
    pp = e_o5(prog(tl, 4.8, 1.0))
    if pp > 0:
        pw = AS.t_date.w + 140; ph = 150
        if not hasattr(AS, 'pill'): AS.pill = pill_sprite(int(pw), ph, RED)
        cyp = 1745 + (1 - pp) * 60
        AS.pill.draw(cv, W/2, cyp, 1.0, pp, sx=lerp(.6, 1, pp))
        AS.t_date.draw(cv, W/2, cyp + 4, 1, clamp(pp * 1.4 - .3))

def shine_mask_area(cv, rect, p):
    # brighten only bright (logo) pixels inside rect along a sweeping band
    x0, y0, x1, y1 = [int(v) for v in rect]
    roi = cv[y0:y1, x0:x1]
    lum = roi.mean(2, keepdims=True)
    m = np.clip((lum - 0.35) / 0.4, 0, 1)
    hh, ww = roi.shape[:2]
    yy, xx = np.mgrid[0:hh, 0:ww].astype(np.float32)
    pos = lerp(-0.3 * (ww + hh), 1.2 * (ww + hh), e_io3(p))
    band = np.exp(-(((xx + yy * .5) - pos) / 140)**2)[..., None]
    roi += (1 - roi) * band * m * 0.75

def draw_outro(cv, tl, dur):
    draw_bg(cv, tl)
    out = e_i3(prog(tl, dur - 1.6, 1.4))  # everything fades -> clean bg for loop
    A_ = 1 - out
    lx = 1290
    p1 = e_o5(prog(tl, 0.5, 1.2))
    AS.logo_deco20.draw(cv, lx, 560 + (1 - p1) * 50, 0.36, p1 * A_)
    p2 = e_o5(prog(tl, 0.8, 1.2))
    AS.logo_sf.draw(cv, lx, 1130 + (1 - p2) * 50, 0.5, p2 * A_)
    p3 = e_o5(prog(tl, 1.4, 1.0))
    if not hasattr(AS, 'pill2'): AS.pill2 = pill_sprite(int(AS.t_date.w * .66 + 110), 112, RED)
    AS.pill2.draw(cv, lx, 1560 + (1 - p3) * 40, 1.0, p3 * A_)
    AS.t_date.draw(cv, lx, 1563 + (1 - p3) * 40, 0.66, clamp(p3 * 1.4 - .3) * A_)
    # right column: store + app
    rx = 2980
    q1 = e_o5(prog(tl, 1.6, 1.0)); AS.t_wait.draw(cv, rx, 470 + (1 - q1) * 40, 1, q1 * A_)
    q2 = e_o5(prog(tl, 1.8, 1.0)); AS.t_city.draw(cv, rx, 620 + (1 - q2) * 50, 1, q2 * A_)
    q3 = e_o5(prog(tl, 2.0, 1.0)); AS.t_addr.draw(cv, rx, 780 + (1 - q3) * 50, 1, q3 * A_)
    ln = e_o5(prog(tl, 2.0, 1.0)) * A_
    if ln > 0:
        lw = int(820 * ln); cv[880:886, rx - lw // 2: rx + lw // 2] = cv[880:886, rx - lw // 2: rx + lw // 2] * (1 - ln) + ICE * ln
    q4 = e_o5(prog(tl, 2.4, 1.0))
    qs = 0.62
    draw_shadow(cv, AS.qr_sh, rx, 1330 + (1 - q4) * 60, qs, .6 * q4 * A_, dy=20)
    AS.qr.draw(cv, rx, 1330 + (1 - q4) * 60, qs, q4 * A_)
    AS.t_app.draw(cv, rx, 1680 + (1 - q4) * 60, 1, q4 * A_)
    # vertical divider
    dv = e_o3(prog(tl, 1.2, 1.2)) * A_
    if dv > 0:
        hh = int(1200 * dv); y0 = 1080 - hh // 2 - 40
        cv[y0:y0 + hh, 2150:2153] = cv[y0:y0 + hh, 2150:2153] * (1 - .5 * dv) + ICE * .5 * dv

# ---------------------------------------------------------------- spots
def spot_frame(spot, tl):
    key = spot['key']; d = S + '/spot_' + key
    n = int(round(clamp(tl, 0, spot['dur'] - 1 / FPS) * FPS))
    files = AS.spots.get(key)
    if files is None:
        files = sorted(glob.glob(d + '/*.png')); AS.spots[key] = files
    n = min(n, len(files) - 1)
    im = cv2.imread(files[n], cv2.IMREAD_COLOR)[:, :, ::-1].astype(np.float32) / 255
    up = cv2.resize(im, (W, H), interpolation=cv2.INTER_LANCZOS4)
    bl = cv2.GaussianBlur(up, (0, 0), 1.6)
    up = np.clip(up + (up - bl) * 0.45, 0, 1)
    return up

def draw_spot(cv, spot, tl):
    cv[:] = spot_frame(spot, tl)

# ---------------------------------------------------------------- compositor
def scene_draw(cv, sc, tg):
    kind, st, du, pl = sc
    tl = tg - st
    if kind == 'intro': draw_intro(cv, tl)
    elif kind == 'pages': draw_pages_block(cv, tl, pl, du)
    elif kind == 'spot': draw_spot(cv, pl, tl)
    elif kind == 'outro': draw_outro(cv, tl, du)

def wipe_mask(p):
    """boundary sweeps right->left: left of it old scene, then a white + ice-blue band, then new scene."""
    ys = np.arange(H, dtype=np.float32)[:, None]; xs = np.arange(W, dtype=np.float32)[None, :]
    X = lerp(W + 1100, -1100, e_io3(p)) + 150 * np.sin(ys / H * math.pi * 1.25 + 0.6) + (ys - H/2) * 0.32
    d = xs - X
    def step(e): return np.clip((d - e + 40) / 80, 0, 1)
    s0, s1, s2 = step(0), step(46), step(150)
    return s0, s1, s2

def render(tg):
    cv = np.empty((H, W, 3), np.float32)
    for b in range(1, len(SEQ)):
        tb = SEQ[b][1]
        if tb - WIPE/2 <= tg < tb + WIPE/2:
            p = (tg - (tb - WIPE/2)) / WIPE
            a = np.empty_like(cv); bcv = np.empty_like(cv)
            scene_draw(a, SEQ[b-1], tg); scene_draw(bcv, SEQ[b], tg)
            s0, s1, s2 = wipe_mask(p)
            white = (s0 - s1)[..., None]; ice = (s1 - s2)[..., None]; mb = s2[..., None]; ma = (1 - s0)[..., None]
            return a * ma + WHITE * white + hexc('8fc6ea') * ice + bcv * mb
    for sc in SEQ:
        if sc[1] <= tg < sc[1] + sc[2]: break
    scene_draw(cv, sc, tg)
    return cv

def is_fast(tg):
    """frames needing motion blur (page slides, card flights, wipes)"""
    for b in range(1, len(SEQ)):
        if abs(tg - SEQ[b][1]) < WIPE/2 + .05: return 3
    for sc in SEQ:
        if sc[0] != 'pages': continue
        tl = tg - sc[1]
        if not (0 <= tl < sc[2]): continue
        for idx, (pi, ps) in enumerate(sc[3]):
            tr = tl - ps
            if 0 <= tr < 1.15: return 5          # page slide
            ncard = len(PAGES[pi]['cards'])
            for ci in range(ncard):
                c0 = 2.0 if pi == 0 else 2.0 + 4.0 * ci
                if 0.05 <= tr - c0 < 0.8: return 4  # card flight
    return 1

def render_mb(tg):
    return render(tg)
    k = is_fast(tg)
    if k == 1: return render(tg)
    shutter = 0.5 / FPS
    acc = None
    for i in range(k):
        ts = tg + (i / (k - 1) - 0.5) * shutter
        f = render(ts)
        acc = f if acc is None else acc + f
    return acc / k

def to8(f):
    return (np.clip(f, 0, 1) * 255 + 0.5).astype(np.uint8)

if __name__ == '__main__':
    mode = sys.argv[1]
    if mode == 'info':
        for s in SEQ: print(s[0], round(s[1], 2), round(s[2], 2))
        print('TOTAL', TOTAL); sys.exit()
    setup()
    if mode == 'frame':
        for tt in sys.argv[3:]:
            f = render_mb(float(tt))
            Image.fromarray(to8(f)).save(f'{sys.argv[2]}_{float(tt):07.2f}.png')
    elif mode == 'chunk':
        i, n, out = int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
        N = int(round(TOTAL * FPS)); a = N * i // n; b = N * (i + 1) // n
        if len(sys.argv) > 6: a, b = int(sys.argv[5]), int(sys.argv[6])
        enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                                '-c:v', 'libx264', '-preset', 'medium', '-crf', '14', '-maxrate', '60M', '-bufsize', '120M',
                                '-profile:v', 'high', '-level', '5.1', '-pix_fmt', 'yuv420p', '-g', '50', '-keyint_min', '50', '-sc_threshold', '0',
                                '-x264-params', 'threads=2', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709',
                                '-vf', 'scale=out_color_matrix=bt709:out_range=tv', out], stdin=subprocess.PIPE)
        import time; t0 = time.time()
        for fi in range(a, b):
            enc.stdin.write(to8(render_mb(fi / FPS)).tobytes())
            if (fi - a) % 50 == 0: print(f'chunk {i}: {fi - a}/{b - a}  {time.time() - t0:.0f}s', flush=True)
        enc.stdin.close(); enc.wait()
        print('done', i)
