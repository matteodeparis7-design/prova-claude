#!/usr/bin/env python3
"""Superfreddo 4K flyer video - VERSION B (light, energetic, product-hero style).
usage: render_b.py info | frame <prefix> <t>... | chunk <i> <n> <out.mp4> [a b]"""
import os, sys, math, subprocess, glob, time
import numpy as np, cv2, pymupdf
from PIL import Image, ImageDraw, ImageFont
_argv = sys.argv; sys.argv = ['x']
import render as R
sys.argv = _argv
from render import (Sprite, rounded_mask, shadow_sprite, load_png_sprite, render_clip, hexc,
                    clamp, lerp, prog, e_io3, e_io4, e_o3, e_o5, e_i3, e_oback, W, H, FPS, SHUT, FONT, DOC, PW, PH)
sys.path.insert(0, R.S)
import cutout as CUT

S = R.S; A = R.A
NAVY = hexc('16324a'); RED = hexc('e3232c'); WHITE = hexc('ffffff'); BLUE = hexc('2f86c8'); ICE = hexc('a9d3f0')
ICEBG_TOP, ICEBG_BOT = hexc('f6fbff'), hexc('d3e8f7')
FOOT_H = 150

# ------------------------------------------------------------------ helpers
def font(w, s): return ImageFont.truetype(FONT[w], s)

def text_img(txt, size, weight, color, track=0):
    f = font(weight, size)
    widths = [f.getlength(c) for c in txt]
    tw = int(sum(widths) + track * max(0, len(txt) - 1)) + 10
    asc, desc = f.getmetrics()
    im = Image.new('RGBA', (tw, asc + desc + 10), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    x = 5
    for c, wd in zip(txt, widths):
        d.text((x, 5), c, font=f, fill=tuple(color) + (255,)); x += wd + track
    return im

def tsprite(txt, size, weight=800, color=(255, 255, 255), track=0):
    im = text_img(txt, size, weight, color, track)
    bb = im.getbbox() or (0, 0, 1, 1)
    sp = Sprite(np.asarray(im, np.float32)[:, :bb[2] + 3])
    sp.ink_top, sp.ink_bot = bb[1], bb[3]
    return sp

def c255(c): return tuple(int(round(v * 255)) for v in c)

def draw_rot(cv, sp, cx, cy, scale, ang=0.0, alpha=1.0, mb=None, tint=None):
    """sprite draw with rotation (degrees) and optional directional motion blur"""
    if alpha <= 0.003 or scale <= 0: return
    if abs(ang) < 0.01: return sp.draw(cv, cx, cy, scale, alpha, mb=mb, tint=tint)
    L = 0
    while L + 1 < len(sp.levels) and scale <= (1 / math.sqrt(2)) ** (L + 1) * 1.0001: L += 1
    lv = sp.levels[L]; lh, lw = lv.shape[:2]
    k = sp.w * scale / lw
    th = math.radians(ang); c, s = math.cos(th), math.sin(th)
    hw, hh = sp.w * scale / 2, sp.h * scale / 2
    ex = abs(hw * c) + abs(hh * s); ey = abs(hw * s) + abs(hh * c)
    pad = 4 + (int(abs(mb[0]) / 2 + abs(mb[1]) / 2) if mb else 0)
    X0, Y0 = max(0, int(cx - ex) - pad), max(0, int(cy - ey) - pad)
    X1, Y1 = min(W, int(cx + ex) + pad), min(H, int(cy + ey) + pad)
    if X1 <= X0 or Y1 <= Y0: return
    # dest = R * k * (u + .5 - lw/2) + (cx, cy) - .5
    a, b_ = k * c, -k * s; d, e = k * s, k * c
    ox = cx - 0.5 - X0 + (a * (0.5 - lw / 2) + b_ * (0.5 - lh / 2))
    oy = cy - 0.5 - Y0 + (d * (0.5 - lw / 2) + e * (0.5 - lh / 2))
    M = np.array([[a, b_, ox], [d, e, oy]], np.float32)
    interp = cv2.INTER_CUBIC if k > 1.01 else cv2.INTER_LINEAR
    src = cv2.warpAffine(lv, M, (X1 - X0, Y1 - Y0), flags=interp, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    if interp == cv2.INTER_CUBIC: np.clip(src, 0, 1, out=src)
    if mb is not None and math.hypot(*mb) >= 1.5:
        BL = math.hypot(*mb); kk = int(math.ceil(BL)) | 1
        ker = np.zeros((kk, kk), np.float32); cc = kk // 2
        for j in range(4 * kk):
            f = j / (4 * kk - 1) - .5
            ker[int(round(cc + mb[1] / BL * f * (kk - 1))), int(round(cc + mb[0] / BL * f * (kk - 1)))] += 1
        src = cv2.filter2D(src, -1, ker / ker.sum(), borderType=cv2.BORDER_CONSTANT)
    if tint is not None: src[..., :3] = tint * src[..., 3:4]
    roi = cv[Y0:Y1, X0:X1]; al = src[..., 3:4] * alpha
    roi *= 1 - al; roi += src[..., :3] * alpha

def draw_persp(cv, sp, quad, alpha=1.0, approx_scale=1.0, tint=None):
    quad = np.array(quad, np.float32)
    X0, Y0 = max(0, int(quad[:, 0].min()) - 2), max(0, int(quad[:, 1].min()) - 2)
    X1, Y1 = min(W, int(quad[:, 0].max()) + 2), min(H, int(quad[:, 1].max()) + 2)
    if X1 <= X0 or Y1 <= Y0 or alpha <= 0: return
    L = 0
    while L + 1 < len(sp.levels) and approx_scale <= (1 / math.sqrt(2)) ** (L + 1) * 1.0001: L += 1
    lv = sp.levels[L]; lh, lw = lv.shape[:2]
    srcq = np.array([[0, 0], [lw, 0], [lw, lh], [0, lh]], np.float32)
    Hm = cv2.getPerspectiveTransform(srcq, quad - np.array([X0, Y0], np.float32))
    src = cv2.warpPerspective(lv, Hm, (X1 - X0, Y1 - Y0), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    if tint is not None: src[..., :3] = tint * src[..., 3:4]
    roi = cv[Y0:Y1, X0:X1]; al = src[..., 3:4] * alpha
    roi *= 1 - al; roi += src[..., :3] * alpha

def roty_quad(cx, cy, w, h, deg, f=3600):
    th = math.radians(deg); out = []
    for (X, Y) in [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]:
        x = X * math.cos(th); z = X * math.sin(th); p = f / (f + z)
        out.append((cx + x * p, cy + Y * p))
    return out

def recolor_logo(path, white_to, blue_to):
    im = np.asarray(Image.open(path).convert('RGBA'), np.float32)
    rgb = im[..., :3]; a = im[..., 3:4]
    k = np.clip((rgb[..., 0:1] - 150) / (255 - 150), 0, 1)  # 1 = white parts, 0 = light blue parts
    out = white_to * 255 * k + blue_to * 255 * (1 - k)
    return Sprite(np.dstack([out, a[..., 0]]))

def radial_sprite(r, col, power=2.0):
    s = int(2 * r) | 1; yy, xx = np.mgrid[0:s, 0:s].astype(np.float32); c = s / 2
    d = np.sqrt((xx - c) ** 2 + (yy - c) ** 2) / r
    a = np.clip(1 - d, 0, 1) ** power
    rgba = np.zeros((s, s, 4), np.float32); rgba[..., :3] = col; rgba[..., 3] = a
    return Sprite(rgba)

def snowflake_sprite(r, col, lw):
    s = int(r * 2.3) * 2; ss = 3
    im = Image.new('L', (s * ss, s * ss), 0); d = ImageDraw.Draw(im); c = s * ss / 2
    R_ = r * ss
    for k in range(6):
        a = k * math.pi / 3; x1, y1 = c + R_ * math.cos(a), c + R_ * math.sin(a)
        d.line([(c, c), (x1, y1)], fill=255, width=int(lw * ss))
        for f in (0.45, 0.7):
            bx, by = c + R_ * f * math.cos(a), c + R_ * f * math.sin(a)
            for sgn in (-1, 1):
                a2 = a + sgn * math.pi / 4; l = R_ * (0.28 if f < .6 else 0.2)
                d.line([(bx, by), (bx + l * math.cos(a2), by + l * math.sin(a2))], fill=255, width=int(lw * ss))
    d.ellipse([c - lw * ss * 1.2, c - lw * ss * 1.2, c + lw * ss * 1.2, c + lw * ss * 1.2], fill=255)
    m = np.asarray(im.resize((s, s), Image.LANCZOS), np.float32) / 255
    rgba = np.zeros((s, s, 4), np.float32); rgba[..., :3] = col; rgba[..., 3] = m
    return Sprite(rgba)

def parallelogram_mask(x0, x1, skew):
    """1 where x0(y) < x < x1(y), edges slanted by skew (px per px of height), soft 3px"""
    ys = np.arange(H, dtype=np.float32)[:, None]; xs = np.arange(W, dtype=np.float32)[None, :]
    off = (H - ys) * skew
    a = np.clip((xs - (x0 + off)) / 3 + .5, 0, 1); b = np.clip(((x1 + off) - xs) / 3 + .5, 0, 1)
    return a * b

# ------------------------------------------------------------------ content
def P(i, c): return dict(i=i, c=c)
SEC = {
    1: dict(col=hexc('2b84cf'), col2=hexc('1b5f9e')),
    2: dict(col=hexc('1f78c1'), col2=hexc('124f8a'), label='PAGINA 2 DI 8  ·  PRODOTTI ANNIVERSARIO', l1='PESCATO', l2='CONGELATO'),
    3: dict(col=hexc('f39200'), col2=hexc('d9640a'), label='PAGINA 3 DI 8', l1='SFIZIOSITÀ', l2='CONGELATE'),
    4: dict(col=hexc('f5a000'), col2=hexc('e0700c'), label='PAGINA 4 DI 8', l1='SFIZIOSITÀ', l2='CONGELATE'),
    5: dict(col=hexc('ec6f1d'), col2=hexc('c94612'), label='PAGINA 5 DI 8', l1='PRIMI E', l2='SFIZIOSITÀ'),
    6: dict(col=hexc('ec7ea6'), col2=hexc('cf4f80'), label='PAGINA 6 DI 8', l1='PASTICCERIA', l2='CONGELATA'),
    7: dict(col=hexc('16a5a1'), col2=hexc('0b7676'), label='PAGINA 7 DI 8', l1='GRANDI MARCHE', l2='SURGELATE'),
    8: dict(col=hexc('0f4458'), col2=hexc('08283a'), label='PAGINA 8 DI 8', l1='SUPER', l2='CONCORSO'),
}
GOLD = dict(col=hexc('c8962f'), col2=hexc('8a5f17'))
CARTA = 'CON CARTA FEDELTÀ'; CARTA7 = 'CON CARTA ESSERE DECÒ'
HEROES = {
    1: [dict(kind='photo', x=716, crop=(40, 300, 1205, 900), name=['BURGER', 'DI SALMONE'], extra='100 G AL PZ', price=('1', '29'), unit='12,90 €/KG', tag='IN COPERTINA')],
    2: [dict(kind='trio', items=[(36, 'FINDUS SOFFICINI', 'VARI GUSTI 250 G', ('1', '89')), (39, 'MC CAIN GOLDEN LONG', 'PATATE 750 G', ('1', '69')), (42, 'MAGNUM BOMBONIERA', 'CLASSICA / ASSORTITA 104 G', ('3', '29'))],
             title='PRODOTTI ANNIVERSARIO', sub='DA 20 ANNI LA TUA SCELTA QUOTIDIANA', sec=GOLD),
        dict(kind='cut', x=64, name=['BISTECCA DI TONNO', 'PINNE GIALLE'], price=('14', '50'), unit='AL KG'),
        dict(kind='photo', x=32, crop=(0, 0, 615, 640), name=['ORATA INTERA'], extra='400/600 G CA.', price=('11', '90'), unit='AL KG'),
        dict(kind='cut', x=33, name=['POLPO RICCIO'], extra='MAROCCO T6 · 800/1100 G CA.', price=('18', '90'), unit='AL KG')],
    3: [dict(kind='photo', x=78, crop=(0, 60, 596, 560), name=['COTOLETTA', 'DI POLLO'], extra='CROCCANTE', price=('6', '50'), unit='AL KG'),
        dict(kind='cut', x=89, name=['FILETTI DI PLATESSA', 'PANATI'], extra='120/170 G CA.', price=('8', '90'), unit='AL KG'),
        dict(kind='cut', x=93, name=['CRUNCHY FISH'], extra='MERLUZZO CON CROCCANTE PANATURA', price=('9', '90'), unit='AL KG'),
        dict(kind='cut', x=85, name=['COTOLETTA', 'DI SALMONE'], price=('7', '50'), unit='AL KG')],
    4: [dict(kind='photo', x=105, crop=(0, 40, 829, 760), name=['CHICKEN RINGS', 'CON BACON'], price=('11', '50'), unit='AL KG'),
        dict(kind='cut', x=118, name=['MINI BARCHETTE', 'DI PATATE ROSTI'], price=('6', '20'), unit='AL KG'),
        dict(kind='cut', x=122, name=['CROCCHÈ GRANDE', 'CON MOZZARELLA'], price=('6', '00'), unit='AL KG'),
        dict(kind='cut', x=107, name=['PATATE A SPICCHI', 'PREFRITTE'], price=('1', '99'), unit='AL KG')],
    5: [dict(kind='photo', x=135, crop=(0, 40, 642, 700), name=['CAPPELLETTI', 'AL PROSCIUTTO CRUDO'], price=('5', '90'), unit='AL KG'),
        dict(kind='cut', x=145, name=['SUPPLÌ DI RISO', 'CON RAGÙ'], price=('5', '90'), unit='AL KG'),
        dict(kind='cut', x=141, name=['PIZZA MARGHERITA'], extra='150 G AL PZ', price=('1', '00'), unit='6,67 €/KG'),
        dict(kind='cut', x=150, name=['OLIVE', "ALL'ASCOLANA"], price=('6', '50'), unit='AL KG')],
    6: [dict(kind='photo', x=176, crop=(0, 60, 657, 640), brand='LA DONATELLA', name=['PROFITEROLES', 'BIANCO'], extra='1,2 KG AL PZ', price=('12', '50'), unit='10,42 €/KG'),
        dict(kind='photo', x=163, crop=(40, 60, 752, 620), name=['CORNETTI RIPIENI'], extra='VARI TIPI · 100 G', price=('1', '00'), unit='', note='2 PEZZI'),
        dict(kind='cut', x=177, brand='MARTINUCCI', name=['SOUFFLÈ', 'AL LIMONE'], extra='12 X 100 G', price=('23', '40'), unit='19,50 €/KG'),
        dict(kind='cut', x=187, name=['CORNETTO', 'GUAVA E MARACUJA'], extra='90 G AL PZ', price=('0', '75'), unit='8,33 €/KG')],
    7: [dict(kind='photo', x=216, crop=(0, 120, 596, 700), brand='FROSTA', name=['MINESTRONE', 'CLASSICO'], extra='LA VALLE DEGLI ORTI · 400 G', price=('1', '29'), unit='3,23 €/KG', note=CARTA7),
        dict(kind='cut', x=226, brand='AIA', name=['NUGGETS', 'DI POLLO'], extra='240 G', price=('2', '49'), unit='10,38 €/KG', note=CARTA7),
        dict(kind='cut', x=223, brand='OROGEL', name=['TANTO CUORE', 'CARCIOFI IN SPICCHI'], extra='300 G', price=('2', '19'), unit='7,30 €/KG', note=CARTA7),
        dict(kind='cut', x=220, brand='FINDUS', name=['FILETTI DI PLATESSA', 'IMPANATI'], extra='250 G', price=('5', '19'), unit='20,76 €/KG', note=CARTA7)],
}
for k in (2,):
    for h in HEROES[k][0]['items']: pass
TRIO_NOTE = CARTA

# ------------------------------------------------------------------ timeline
SHOTS = []  # dict(kind, start, dur, ...)
_t = 0.0
def shot(kind, dur, tr='panel', **kw):
    global _t
    SHOTS.append(dict(kind=kind, start=_t, dur=dur, tr=tr, **kw)); _t += dur
shot('intro', 8.0, tr=None)
shot('scroll', 8.0, page=1, first=True)
for h in HEROES[1]: shot('hero', 4.0, page=1, h=h)
def page_block(p):
    shot('opener', 2.0, page=p)
    shot('scroll', 6.0, page=p, tr='reveal')
    for j, h in enumerate(HEROES[p]): shot('hero', 4.0, page=p, h=h, tr=('panel' if j == 0 else 'none'))
for p in (2, 3, 4): page_block(p)
shot('spot', 36.0, spot=R.SPOT1, tr='double')
for p in (5, 6, 7): page_block(p)
shot('spot', 46.0, spot=R.SPOT2, tr='double')
shot('opener', 2.0, page=8, tr='double')
shot('scroll', 6.0, page=8, tr='reveal')
shot('concorso', 8.0, page=8, tr='panel')
shot('outro', 10.0, tr='panel')
TOTAL = _t
TR_D = 0.8

# ------------------------------------------------------------------ assets
class AS_: pass
AS = AS_()

def build_ice_bg():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    u = np.clip(yy / H * 0.7 + xx / W * 0.3, 0, 1)[..., None]
    bg = ICEBG_TOP * (1 - u) + ICEBG_BOT * u
    for (gx, gy, r, c, a) in [(3200, 300, 1500, WHITE, .55), (600, 1900, 1400, hexc('bcdcf3'), .45)]:
        d = np.exp(-((xx - gx) ** 2 + (yy - gy) ** 2) / (2 * (r / 2) ** 2))[..., None]
        bg = bg * (1 - a * d) + c * a * d
    # big soft diagonal bands
    for (x0, wdt, c, a) in [(2300, 700, WHITE, .35), (3100, 260, hexc('c7e2f6'), .35)]:
        d = (xx - x0) + (yy - H) * 0.45
        m = np.clip(1 - np.abs(d) / wdt, 0, 1)[..., None] ** 1.5
        bg = bg * (1 - a * m) + c * a * m
    rng = np.random.default_rng(1)
    bg += (rng.random((H, W, 1), np.float32) - .5) / 255 * 1.5
    return np.clip(bg, 0, 1).astype(np.float32)

def build_color_bg(col, col2):
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    u = np.clip((xx / W) * 0.55 + (yy / H) * 0.45, 0, 1)[..., None]
    bg = col * (1 - u) + col2 * u
    d = np.exp(-((xx - 1250) ** 2 + (yy - 1050) ** 2) / (2 * 1300 ** 2))[..., None]
    bg = bg * (1 - .30 * d) + WHITE * .30 * d
    for (x0, wdt, a) in [(1900, 900, .07), (3300, 220, .10), (500, 160, .06)]:
        dd = (xx - x0) + (yy - H) * 0.45
        m = np.clip(1 - np.abs(dd) / wdt, 0, 1)[..., None]
        bg = bg * (1 - a * m) + WHITE * a * m
    v = ((xx - W / 2) / (W * .7)) ** 2 + ((yy - H / 2) / (H * .8)) ** 2
    bg *= (1 - 0.18 * np.clip(v, 0, 1.5)[..., None] / 1.5)
    rng = np.random.default_rng(2)
    bg += (rng.random((H, W, 1), np.float32) - .5) / 255 * 1.5
    return np.clip(bg, 0, 1).astype(np.float32)

class Cache:
    def __init__(self, fn, n=3): self.fn, self.n, self.c = fn, n, {}
    def __getitem__(self, k):
        if k not in self.c:
            if len(self.c) >= self.n: self.c.pop(next(iter(self.c)))
            self.c[k] = self.fn(k)
        return self.c[k]

def colbg_key(k):
    s = GOLD if k == 'gold' else SEC[k]
    return build_color_bg(s['col'], s['col2'])

PAGE_SW = 1720  # on-screen width of scrolling page
def build_page(i):
    z = PAGE_SW / PW * 1.35
    rgb = render_clip(i - 1, (0, 0, PW, PH), z)
    sp = Sprite(np.dstack([rgb, np.ones(rgb.shape[:2], np.float32)])); sp.base = PAGE_SW / rgb.shape[1]
    return sp

def photo_sprite(x, crop, maxw=1750, maxh=1320):
    im = Image.open(f'{S}/cut/photo{x}.png').convert('RGB').crop(crop)
    w, h = im.size; s = min(maxw / w, maxh / h)
    W2, H2 = int(w * s), int(h * s)
    a = cv2.resize(np.asarray(im, np.float32), (W2, H2), interpolation=cv2.INTER_LANCZOS4)
    bl = cv2.GaussianBlur(a, (0, 0), 1.3); a = np.clip(a + (a - bl) * 0.5, 0, 255) / 255
    bw = 26
    fr = np.ones((H2 + 2 * bw, W2 + 2 * bw, 3), np.float32)
    fr[bw:bw + H2, bw:bw + W2] = a
    m = rounded_mask(fr.shape[1], fr.shape[0], 46)
    sp = Sprite(np.dstack([fr, m]))
    sp.shadow = shadow_sprite(fr.shape[1], fr.shape[0], 0, 55)
    return sp

def cut_sprite(x, maxw=1900, maxh=1250):
    p = f'{S}/cut/x{x}.png'
    im = Image.open(p)
    a = np.asarray(im, np.float32)
    h, w = a.shape[:2]; s = min(maxw / w, maxh / h, 2.2)
    if s < 1: a = cv2.resize(a, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    elif s > 1: a = np.clip(cv2.resize(a, (int(w * s), int(h * s)), interpolation=cv2.INTER_CUBIC), 0, 255)
    sp = Sprite(a)
    # contact shadow: blurred alpha
    al = a[..., 3] / 255
    sh = cv2.GaussianBlur(al, (0, 0), 30)
    rgba = np.zeros(a.shape, np.float32); rgba[..., 3] = sh * 0.55
    sp.shadow = Sprite(rgba)
    return sp

def price_sprite(ip, cp, unit, note=None, scale=1.0, tight=False):
    S_ = scale
    fi, fc, fe = font(900, int(340 * S_)), font(900, int(170 * S_)), font(800, int(96 * S_))
    pc = c255(RED)
    bi = fi.getbbox(ip); bc = fc.getbbox(cp); bcm = fi.getbbox(','); be = fe.getbbox('€')
    wi = bi[2] - bi[0]; wc = bc[2] - bc[0]; wcm = bcm[2] - bcm[0]; we = be[2] - be[0]
    cap = bi[3] - bi[1]
    pad = int(66 * S_); gap = int(10 * S_)
    colw = max(wc, we)
    g1, g2 = (int(2 * S_), -int(wcm * 0.55)) if tight else (gap, gap)
    bw = pad + wi + g1 + wcm + g2 + colw + pad
    bh = pad + cap + pad
    strips = []
    if unit: strips.append((unit, c255(NAVY)))
    if note: strips.append((note, c255(RED) if note != unit else c255(NAVY)))
    fs = font(800, int(54 * S_)); sh_ = int(92 * S_)
    sw = [fs.getbbox(t)[2] - fs.getbbox(t)[0] + int(70 * S_) for t, _ in strips]
    W_ = max([bw] + sw)
    Ht = bh + len(strips) * (sh_ - int(10 * S_)) + int(10 * S_)
    im = Image.new('RGBA', (W_, Ht), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    ox = (W_ - bw) // 2
    d.rounded_rectangle([ox, 0, ox + bw - 1, bh - 1], int(56 * S_), fill=(255, 255, 255, 255))
    y = pad - bi[1]; x = ox + pad - bi[0]
    d.text((x, y), ip, font=fi, fill=pc)
    x2 = ox + pad + wi + g1
    d.text((x2 - bcm[0], y), ',', font=fi, fill=pc)
    x3 = x2 + wcm + g2
    d.text((x3 + (colw - wc) // 2 - bc[0], pad - bc[1]), cp, font=fc, fill=pc)
    ey = pad + (bc[3] - bc[1]) + int(22 * S_)
    d.text((x3 + (colw - we) // 2 - be[0], ey - be[1]), '€', font=fe, fill=pc)
    yy = bh - int(22 * S_)
    for (t, col), w_ in zip(strips, sw):
        bb = fs.getbbox(t); sx = (W_ - w_) // 2
        d.rounded_rectangle([sx, yy, sx + w_, yy + sh_], int(22 * S_), fill=col + (255,))
        d.text((sx + int(35 * S_) - bb[0], yy + (sh_ - (bb[3] - bb[1])) // 2 - bb[1]), t, font=fs, fill=(255, 255, 255))
        yy += sh_ - int(10 * S_)
    a = np.asarray(im, np.float32)
    sp = Sprite(a); sp.badge_h = bh
    sp.shadow = shadow_sprite(bw, bh, 0, 30)
    return sp

def build_hero(key):
    p, j = key
    h = HEROES[p][j]
    o = {}
    if h['kind'] == 'cut': o['img'] = cut_sprite(h['x'])
    elif h['kind'] == 'photo': o['img'] = photo_sprite(h['x'], h['crop'])
    elif h['kind'] == 'trio':
        o['items'] = []
        for (x, nm, sub, pr) in h['items']:
            sp = cut_sprite(x, 900, 760)
            o['items'].append((sp, tsprite(nm, 62, 800, (255, 255, 255), 2), tsprite(sub, 44, 600, (255, 240, 210), 2),
                               price_sprite(pr[0], pr[1], '', note=TRIO_NOTE, scale=0.55, tight=True)))
        o['title'] = tsprite(h['title'], 150, 900, (255, 255, 255), 3)
        o['sub'] = tsprite(h['sub'], 58, 600, (255, 236, 196), 8)
        return o
    o['brand'] = tsprite(h['brand'], 78, 700, (255, 255, 255), 10) if h.get('brand') else None
    lines = []
    for ln in h['name']:
        size = 172
        while True:
            sp = tsprite(ln, size, 900, (255, 255, 255), 2)
            if sp.w < 1380 or size < 80: break
            size -= 6
        lines.append(sp)
    o['name'] = lines
    o['extra'] = tsprite(h['extra'], 60, 600, (255, 255, 255), 5) if h.get('extra') else None
    o['price'] = price_sprite(h['price'][0], h['price'][1], h.get('unit', ''), note=h.get('note'), scale=1.3)
    o['tag'] = tsprite(h['tag'], 50, 800, c255(RED), 10) if h.get('tag') else None
    return o

def setup():
    AS.ice = build_ice_bg()
    AS.colbg = Cache(colbg_key, 2)
    AS.pages = Cache(build_page, 2)
    AS.heroes = Cache(build_hero, 6)
    AS.logo20 = recolor_logo(A + '/logo_deco20.png', NAVY, BLUE)
    AS.logosf = recolor_logo(A + '/logo_superfreddo.png', NAVY, BLUE)
    AS.logo20w = load_png_sprite(A + '/logo_deco20.png')
    AS.logosfw = load_png_sprite(A + '/logo_superfreddo.png')
    AS.concorso = load_png_sprite(A + '/logo_concorso.png')
    AS.flake = [snowflake_sprite(r, WHITE, max(2.5, r / 22)) for r in (40, 70, 110, 160)]
    AS.flake_blue = [snowflake_sprite(r, hexc('9cc9ec'), max(2.5, r / 22)) for r in (40, 70, 110, 160)]
    AS.glow = radial_sprite(400, WHITE, 1.6)
    rng = np.random.default_rng(11)
    AS.fl = [dict(x=rng.random() * W, y=rng.random() * H, k=int(rng.integers(0, 4)), rot=rng.random() * 60, vr=rng.uniform(-6, 6),
                  vy=rng.uniform(8, 28), vx=rng.uniform(-8, 8), a=rng.uniform(.10, .26)) for _ in range(22)]
    # texts
    AS.foot_date = tsprite('OFFERTE VALIDE DAL 13 AL 22 OTTOBRE 2026', 48, 700, c255(NAVY), 5)
    AS.foot_store = tsprite('COLLEFERRO · VIA DEI PIOPPI, 24', 46, 700, c255(RED), 4)
    AS.t_vol = tsprite('IL NUOVO VOLANTINO', 74, 700, c255(BLUE), 22)
    AS.t_date1 = tsprite('OFFERTE VALIDE', 60, 700, (255, 255, 255), 8)
    AS.t_date2 = tsprite('DAL 13 AL 22 OTTOBRE 2026', 104, 900, (255, 255, 255), 3)
    AS.t_wait = tsprite('TI ASPETTIAMO A', 70, 700, c255(BLUE), 16)
    AS.t_city = tsprite('COLLEFERRO', 230, 900, c255(NAVY), 4)
    AS.t_addr = tsprite('VIA DEI PIOPPI, 24', 100, 700, c255(NAVY), 8)
    AS.t_app = tsprite("SCARICA L'APP DECÒ", 54, 800, c255(NAVY), 6)
    qr = render_clip(7, (424, 404, 580, 494), 9.0)
    AS.qr = Sprite(np.dstack([qr, rounded_mask(qr.shape[1], qr.shape[0], 40)])); AS.qr_sh = shadow_sprite(qr.shape[1], qr.shape[0], 0, 40)
    AS.openers = {}
    for p in range(2, 9):
        s = SEC[p]
        def fit(txt):
            size = 330
            while True:
                sp = tsprite(txt, size, 900, (255, 255, 255), 4)
                if sp.w < 3000 or size < 120: return sp
                size -= 10
        AS.openers[p] = (tsprite(s['label'], 58, 700, (255, 255, 255), 12), fit(s['l1']), fit(s['l2']),
                         tsprite(f'{p:02d}', 900, 900, (255, 255, 255), 0))
    AS.side = {}
    for p in range(1, 9):
        s = SEC[p]
        num = tsprite(f'{p:02d}', 520, 900, c255(s['col']), 0)
        t1 = tsprite(s.get('l1', 'VOLANTINO'), 96, 900, c255(NAVY), 2)
        t2 = tsprite(s.get('l2', 'SUPERFREDDO'), 96, 900, c255(s['col']), 2)
        lab = tsprite(f'PAGINA {p} DI 8', 46, 700, c255(BLUE), 10)
        AS.side[p] = (num, t1, t2, lab)
    # concorso
    hdr = render_clip(7, (0, 127, PW, 262), 2400 / PW)
    AS.prizes = Sprite(np.dstack([hdr, rounded_mask(hdr.shape[1], hdr.shape[0], 30)]))
    AS.c_lines = [tsprite(t, s, w, c, tr) for (t, s, w, c, tr) in [
        ('OGNI 20 € DI SPESA', 120, 900, (255, 255, 255), 3),
        ('RICEVI UN GETTONE DI GIOCO', 92, 800, c255(hexc('ff5a5f')), 3),
        ("GIOCA SULL'APP DECÒ E SCOPRI SUBITO SE HAI VINTO!", 66, 700, (255, 255, 255), 3),
        ('CONCORSO VALIDO DAL 14 SETTEMBRE AL 1° NOVEMBRE 2026', 48, 600, c255(ICE), 6)]]
    AS.spots = {}

# ------------------------------------------------------------------ common layers
def draw_flakes(cv, t, blue=False, alpha=1.0):
    fl = AS.flake_blue if blue else AS.flake
    for q in AS.fl:
        x = (q['x'] + q['vx'] * t) % (W + 400) - 200; y = (q['y'] + q['vy'] * t) % (H + 400) - 200
        draw_rot(cv, fl[q['k']], x, y, 1.0, q['rot'] + q['vr'] * t, q['a'] * alpha)

FOOT_KINDS = ('scroll', 'opener', 'hero', 'concorso')
FOOT_DEFER = [False]
def draw_footer(cv, a=1.0, dark=False):
    if a <= 0 or FOOT_DEFER[0]: return
    y0 = H - FOOT_H
    band = cv[y0:]
    band *= 1 - 0.94 * a; band += WHITE * 0.94 * a
    cv[y0:y0 + 8, :] = cv[y0:y0 + 8, :] * (1 - a) + RED * a
    cy = y0 + FOOT_H / 2 + 4
    sc = 0.115
    AS.logosf.draw(cv, 250 + AS.logosf.w * sc / 2, cy, sc, a)
    x = 250 + AS.logosf.w * sc + 80
    AS.foot_date.draw(cv, x + AS.foot_date.w / 2, cy, 1, a)
    AS.foot_store.draw(cv, W - 250 - AS.foot_store.w / 2, cy, 1, a)

def ribbon(cv, x0, y0, w, h, col, a, skew=0.35):
    """slanted parallelogram ribbon, left-top at (x0,y0)"""
    if a <= 0 or w <= 1: return
    X0, X1 = int(max(0, x0 - h * skew - 2)), int(min(W, x0 + w + 2))
    Y0, Y1 = int(max(0, y0)), int(min(H, y0 + h))
    if X1 <= X0 or Y1 <= Y0: return
    ys = np.arange(Y0, Y1, dtype=np.float32)[:, None]; xs = np.arange(X0, X1, dtype=np.float32)[None, :]
    off = (y0 + h - ys) * skew - h * skew
    m = np.clip((xs - (x0 + off)) + .5, 0, 1) * np.clip(((x0 + w + off) - xs) + .5, 0, 1)
    m = (m * a)[..., None]
    roi = cv[Y0:Y1, X0:X1]; roi *= 1 - m; roi += col * m

# ------------------------------------------------------------------ shots
def d_intro(cv, t, sh):
    cv[:] = AS.ice; draw_flakes(cv, t, blue=True, alpha=.9)
    # swoosh ribbons sweeping across
    for i, (col, hgt, y, dl) in enumerate([(BLUE, 120, 1500, 0.0), (ICE, 60, 1650, 0.08), (RED, 26, 1735, 0.16)]):
        p = e_io3(prog(t, 0.15 + dl, 1.2))
        x0 = lerp(-2600, 4200, p)
        ribbon(cv, x0, y, 2400, hgt, col, 0.9)
    p1 = prog(t, 0.9, 0.9)
    if p1 > 0:
        s = 0.40 * e_oback(p1, 1.6)
        AS.logo20.draw(cv, W / 2, 560, max(s, 0.001), clamp(p1 * 3))
    p2 = prog(t, 1.5, 1.2)
    if p2 > 0:
        tmp = np.zeros((H, W, 3), np.float32); tma = np.zeros((H, W, 3), np.float32)
        sc = 0.64; cy = 1130
        AS.logosf.draw(tmp, W / 2, cy, sc, 1.0); AS.logosf.draw(tma, W / 2, cy, sc, 1.0, tint=np.ones(3, np.float32))
        wsf = AS.logosf.w * sc; x0 = W / 2 - wsf / 2 - 100
        edge = lerp(x0, x0 + wsf + 300, e_io3(p2))
        m = np.clip((edge - np.arange(W, dtype=np.float32)) / 140, 0, 1)[None, :, None]
        cv *= 1 - tma[..., :1] * m; cv += tmp * m
    pv = e_o5(prog(t, 2.9, 0.9))
    if pv > 0: AS.t_vol.draw(cv, W / 2, 1560 + (1 - pv) * 50, 1, pv)
    pr = e_o5(prog(t, 3.3, 0.8))
    if pr > 0:
        w = (AS.t_date2.w + 260) * pr
        ribbon(cv, W / 2 - (AS.t_date2.w + 260) / 2 + 40, 1660, w, 190, RED, 1.0)
        a = clamp(prog(t, 3.6, 0.5))
        AS.t_date2.draw(cv, W / 2, 1755, 1, a)

def page_quad(t, dur, first):
    sp = AS.pages[SH_CUR['page']]
    pw = PAGE_SW; ph = pw * PH / PW
    ent = 1.3
    pin = e_o3(prog(t, 0, ent))
    ang = lerp(38, 0, pin); scl = lerp(0.82, 1.0, pin)
    top0, top1 = 150, H - FOOT_H - 70 - ph
    ps = e_io3(prog(t, ent + 0.3, dur - ent - 0.9))
    top = lerp(top0, top1, ps)
    cy = top + ph / 2
    cx = W / 2 + lerp(700, 0, pin)
    return sp, roty_quad(cx, cy + (1 - pin) * 40, pw * scl, ph * scl, ang), scl, (cx, cy, pw, ph)

SH_CUR = {}
def d_scroll(cv, t, sh):
    p = sh['page']; SH_CUR['page'] = p
    cv[:] = AS.ice; draw_flakes(cv, t, blue=True, alpha=.7)
    # side panels
    num, t1, t2, lab = AS.side[p]
    ain = e_o5(prog(t, 0.4, 0.9))
    lx = 140
    num.draw(cv, lx + num.w / 2 + (1 - ain) * -80, 560, 1, ain * 0.95)
    lab.draw(cv, lx + 10 + lab.w / 2 + (1 - ain) * -60, 960, 1, ain)
    a2 = e_o5(prog(t, 0.55, 0.9))
    sc1 = min(1, 820 / t1.w); sc2 = min(1, 820 / t2.w)
    t1.draw(cv, lx + 10 + t1.w * sc1 / 2 + (1 - a2) * -60, 1080, sc1, a2)
    t2.draw(cv, lx + 10 + t2.w * sc2 / 2 + (1 - a2) * -60, 1080 + 110, sc2, a2)
    # right side: logo + ribbon
    rx = W - 520
    a3 = e_o5(prog(t, 0.6, 0.9))
    AS.logo20.draw(cv, rx, 520 + (1 - a3) * 60, 0.24, a3)
    AS.logosf.draw(cv, rx, 900 + (1 - a3) * 60, 0.27, a3)
    a4 = e_o5(prog(t, 0.8, 0.8))
    if a4 > 0:
        rw = AS.t_date2.w * 0.5 + 200
        ribbon(cv, rx - rw / 2 + 45, 1130, rw * a4, 230, RED, 1)
        AS.t_date1.draw(cv, rx, 1192, 0.8, clamp(prog(t, 1.0, .4)))
        AS.t_date2.draw(cv, rx, 1285, 0.5, clamp(prog(t, 1.05, .4)))
    # page
    sp, quad, scl, (cx, cy, pw, ph) = page_quad(t, sh['dur'], sh.get('first'))
    shadow = AS.page_shadow if hasattr(AS, 'page_shadow') else None
    if shadow is None:
        AS.page_shadow = shadow_sprite(int(PAGE_SW), int(PAGE_SW * PH / PW), 0, 60); shadow = AS.page_shadow
    q = np.array(quad); qc = q.mean(0)
    sq = [(x + 0, y + 40) for (x, y) in quad]
    # shadow: draw via perspective of shadow sprite (pad aware)
    pad = shadow.pad
    sx = (PAGE_SW + 2 * pad) / PAGE_SW
    sq2 = [(qc[0] + (x - qc[0]) * sx, qc[1] + 40 + (y - qc[1]) * (1 + 2 * pad / (PAGE_SW * PH / PW))) for (x, y) in quad]
    draw_persp(cv, shadow, sq2, 0.45, approx_scale=scl / shadow.q, tint=np.array([0.05, 0.12, 0.2], np.float32))
    draw_persp(cv, sp, quad, 1.0, approx_scale=sp.base * scl)
    draw_footer(cv)

def d_opener(cv, t, sh):
    p = sh['page']
    cv[:] = AS.colbg[p]; draw_flakes(cv, t, alpha=.8)
    lab, l1, l2, num = AS.openers[p]
    pn = e_o5(prog(t, 0.0, 1.2))
    num.draw(cv, W - 160 - num.w / 2 + (1 - pn) * 300, 1000, 1, 0.10 * pn)
    x = 300
    def line(sp, y, d0):
        pp = e_o5(prog(t, d0, 0.7))
        if pp <= 0: return
        # masked rise: clip by drawing into temp band
        dy = (1 - pp) * sp.h * 0.9
        sp.draw(cv, x + sp.w / 2, y + dy, 1, pp)
    line(lab, 700, 0.15)
    line(l1, 960, 0.22)
    line(l2, 960 + l1.ink_bot - 40, 0.32)
    rb = e_o5(prog(t, 0.2, 0.8))
    ribbon(cv, x, 590, 260 * rb, 22, WHITE, 1)
    draw_footer(cv)

def hero_bg(cv, t, sh):
    key = 'gold' if sh['h'].get('sec') is GOLD else sh['page']
    cv[:] = AS.colbg[key]
    draw_flakes(cv, t + sh['start'], alpha=.9)

def hero_pose(t, dur):
    """product pose: x offset, y offset, rotation, scale, alpha"""
    pin = e_o5(prog(t, 0.0, 0.85)); pout = e_i3(prog(t, dur - 0.55, 0.55))
    x = lerp(1900, 0, pin) - 2600 * pout
    rot = lerp(-12, 0, pin) + 8 * pout
    sc = lerp(0.82, 1, pin) * (1 + 0.035 * e_io3(prog(t, 0.6, dur - 1.0)))
    y = 14 * math.sin(t * 2 * math.pi / 3.2)
    return x, y, rot, sc

def d_hero(cv, t, sh):
    hero_bg(cv, t, sh)
    h = sh['h']; dur = sh['dur']
    o = AS.heroes[(sh['page'], HEROES[sh['page']].index(h))]
    if h['kind'] == 'trio': return d_trio(cv, t, sh, o)
    pcx, pcy = 1180, 1010
    x, y, rot, sc = hero_pose(t, dur)
    x2, _, _, _ = hero_pose(t + SHUT, dur)
    mb = (x2 - x, 0)
    # glow disc
    gp = e_oback(prog(t, 0.05, 0.7), 1.3) * (1 - e_i3(prog(t, dur - 0.5, 0.5)))
    if gp > 0: AS.glow.draw(cv, pcx, pcy, 2.9 * max(gp, 0.01), 0.55)
    img = o['img']
    if h['kind'] == 'photo':
        rot2 = rot - 2.5
        draw_rot(cv, img.shadow, pcx + x + 10, pcy + y + 45, sc * img.shadow.q, rot2, 0.5, mb=mb, tint=np.array([.02, .05, .1], np.float32))
        draw_rot(cv, img, pcx + x, pcy + y, sc, rot2, 1.0, mb=mb)
    else:
        draw_rot(cv, img.shadow, pcx + x + 25, pcy + y + 70, sc, rot, 0.9, mb=mb, tint=np.array([.02, .05, .1], np.float32))
        draw_rot(cv, img, pcx + x, pcy + y, sc, rot, 1.0, mb=mb)
    # text column
    tx = 2270
    tout = e_i3(prog(t, dur - 0.6, 0.45))
    def T(sp, yy, d0, scale=1.0):
        if sp is None: return
        pp = e_o5(prog(t, d0, 0.7))
        a = pp * (1 - tout)
        if a <= 0: return
        sp.draw(cv, tx + sp.w * scale / 2 + (1 - pp) * 160 - tout * 200, yy, scale, a)
    yy = 430
    if o.get('tag'):
        pt = e_o5(prog(t, 0.3, 0.6)) * (1 - tout)
        ribbon(cv, tx - 10, yy - 60, (o['tag'].w + 80) * pt, 100, WHITE, 1)
        T(o['tag'], yy - 8, 0.35); yy += 120
    if o['brand'] is not None: T(o['brand'], yy, 0.35); yy += 110
    for i, sp in enumerate(o['name']):
        T(sp, yy + sp.h / 2 - 30, 0.42 + 0.08 * i); yy += sp.ink_bot - 18
    if o['extra'] is not None: yy += 40; T(o['extra'], yy, 0.6); yy += 70
    # price badge pops
    pr = o['price']
    pp = prog(t, 0.75, 0.6)
    if pp > 0:
        s = e_oback(pp, 2.0) * (1 - tout * 0.6)
        a = clamp(pp * 4) * (1 - tout)
        bx = tx + pr.w / 2; by = max(yy + 110, 1060) + pr.h / 2
        draw_rot(cv, pr.shadow, bx + 10, by - pr.h / 2 + pr.badge_h / 2 + 30, s * pr.shadow.q, -4, 0.45 * a, tint=np.array([.02, .05, .1], np.float32))
        draw_rot(cv, pr, bx, by, max(s, 0.01), -4, a)
    draw_footer(cv)

def d_trio(cv, t, sh, o):
    dur = sh['dur']
    tout = e_i3(prog(t, dur - 0.55, 0.5))
    pt = e_o5(prog(t, 0.1, 0.8))
    o['title'].draw(cv, W / 2, 330 + (1 - pt) * 60 - tout * 60, 1, pt * (1 - tout))
    ps = e_o5(prog(t, 0.25, 0.8))
    o['sub'].draw(cv, W / 2, 470 + (1 - ps) * 40, 1, ps * (1 - tout))
    for i, (img, nm, sub, pr) in enumerate(o['items']):
        cx = 760 + i * 1160; cy = 1060
        d0 = 0.25 + 0.18 * i
        pin = e_o5(prog(t, d0, 0.8))
        x = lerp(1400, 0, pin) - 2600 * e_i3(prog(t, dur - 0.55 + 0.05 * i, 0.5))
        x2 = lerp(1400, 0, e_o5(prog(t + SHUT, d0, 0.8))) - 2600 * e_i3(prog(t + SHUT, dur - 0.55 + 0.05 * i, 0.5))
        y = 10 * math.sin(t * 2 * math.pi / 3 + i)
        rot = lerp(-10, 0, pin)
        draw_rot(cv, img.shadow, cx + x + 20, cy + y + 60, 1, rot, 0.9, mb=(x2 - x, 0), tint=np.array([.05, .03, 0], np.float32))
        draw_rot(cv, img, cx + x, cy + y, 1, rot, 1, mb=(x2 - x, 0))
        pa = e_o5(prog(t, d0 + 0.3, 0.6)) * (1 - tout)
        nm.draw(cv, cx + x * 0.3, 1560 + (1 - pa) * 40, min(1, 1000 / nm.w), pa)
        sub.draw(cv, cx + x * 0.3, 1640 + (1 - pa) * 40, 1, pa)
        pp = prog(t, d0 + 0.55, 0.55)
        if pp > 0:
            s = e_oback(pp, 2.0)
            draw_rot(cv, pr, cx + 300 + x, cy - 300 + y, max(s, .01), -6, clamp(pp * 4) * (1 - tout))
    draw_footer(cv)

def d_concorso(cv, t, sh):
    cv[:] = AS.colbg[8]; draw_flakes(cv, t, alpha=.6)
    dur = sh['dur']; out = e_i3(prog(t, dur - 0.6, 0.5))
    p1 = e_o5(prog(t, 0.1, 0.9))
    AS.concorso.draw(cv, W / 2, 330 + (1 - p1) * 60, 0.62 * lerp(.9, 1, p1), p1 * (1 - out))
    p2 = e_o5(prog(t, 0.5, 1.0))
    sc = 1 + 0.03 * prog(t, 0.5, dur)
    draw_rot(cv, AS.prizes, W / 2 + (1 - p2) * 900, 1000, sc, 0, p2 * (1 - out))
    ys = [1430, 1560, 1680, 1790]
    for i, sp in enumerate(AS.c_lines):
        pp = e_o5(prog(t, 1.4 + 0.5 * i, 0.7))
        sp.draw(cv, W / 2 + (1 - pp) * 120, ys[i], 1, pp * (1 - out))
    draw_footer(cv)

def d_outro(cv, t, sh):
    cv[:] = AS.ice; draw_flakes(cv, t, blue=True, alpha=.8)
    dur = sh['dur']; out = e_i3(prog(t, dur - 1.6, 1.4)); A_ = 1 - out
    lx = 1150
    p1 = e_oback(prog(t, 0.4, 0.8), 1.4)
    AS.logo20.draw(cv, lx, 560, 0.36 * max(p1, .01), clamp(p1 * 3) * A_)
    p2 = e_o5(prog(t, 0.7, 1.0))
    AS.logosf.draw(cv, lx, 1100 + (1 - p2) * 50, 0.48, p2 * A_)
    p3 = e_o5(prog(t, 1.2, 0.9))
    if p3 > 0:
        wdt = AS.t_date2.w * 0.7 + 200
        ribbon(cv, lx - wdt / 2 + 40, 1440, wdt * p3, 150, RED, A_)
        AS.t_date2.draw(cv, lx, 1515, 0.7, clamp(prog(t, 1.5, .4)) * A_)
    rx = 2850
    q1 = e_o5(prog(t, 1.4, .9)); AS.t_wait.draw(cv, rx, 420 + (1 - q1) * 40, 1, q1 * A_)
    q2 = e_o5(prog(t, 1.6, .9)); AS.t_city.draw(cv, rx, 600 + (1 - q2) * 50, 1, q2 * A_)
    q3 = e_o5(prog(t, 1.8, .9)); AS.t_addr.draw(cv, rx, 790 + (1 - q3) * 50, 1, q3 * A_)
    q4 = e_o5(prog(t, 2.2, 1.0))
    draw_rot(cv, AS.qr_sh, rx, 1290 + (1 - q4) * 60 + 20, 0.62 * AS.qr_sh.q, 0, .5 * q4 * A_, tint=np.array([.02, .05, .1], np.float32))
    AS.qr.draw(cv, rx, 1290 + (1 - q4) * 60, 0.62, q4 * A_)
    AS.t_app.draw(cv, rx, 1650 + (1 - q4) * 60, 1, q4 * A_)

def d_spot(cv, t, sh):
    sp = sh['spot']; key = sp['key']
    files = AS.spots.get(key)
    if files is None: files = sorted(glob.glob(S + '/spot_' + key + '/*.png')); AS.spots[key] = files
    n = min(int(round(clamp(t, 0, sp['dur'] - 1 / FPS) * FPS)), len(files) - 1)
    im = cv2.imread(files[n], cv2.IMREAD_COLOR)[:, :, ::-1].astype(np.float32) / 255
    up = cv2.resize(im, (W, H), interpolation=cv2.INTER_LANCZOS4)
    bl = cv2.GaussianBlur(up, (0, 0), 1.6)
    cv[:] = np.clip(up + (up - bl) * 0.45, 0, 1)

DRAW = dict(intro=d_intro, scroll=d_scroll, opener=d_opener, hero=d_hero, concorso=d_concorso, outro=d_outro, spot=d_spot)

def shot_draw(cv, i, tg):
    sh = SHOTS[i]
    if sh['kind'] == 'scroll': SH_CUR['page'] = sh['page']
    DRAW[sh['kind']](cv, tg - sh['start'], sh)

def shot_color(sh):
    if sh['kind'] in ('hero',) and sh['h'].get('sec') is GOLD: return GOLD['col']
    if sh['kind'] in ('hero', 'opener', 'concorso'): return SEC[sh['page']]['col']
    return BLUE

def render(tg):
    cv = np.empty((H, W, 3), np.float32)
    for i in range(1, len(SHOTS)):
        sh = SHOTS[i]; tb = sh['start']; tr = sh['tr']
        if tr in (None, 'none'): continue
        if tb - TR_D / 2 <= tg < tb + TR_D / 2:
            p = (tg - (tb - TR_D / 2)) / TR_D
            a = np.empty_like(cv); b = np.empty_like(cv)
            both = SHOTS[i - 1]['kind'] in FOOT_KINDS and sh['kind'] in FOOT_KINDS
            FOOT_DEFER[0] = both
            shot_draw(a, i - 1, tg); shot_draw(b, i, tg)
            FOOT_DEFER[0] = False
            skew = 0.42
            span = W + H * skew + 600
            X = lerp(-H * skew - 400, W + 300, e_io3(p))
            if tr == 'double':
                bands = [(0, RED), (130, ICE)]
            elif tr == 'reveal':
                bands = [(0, WHITE)]
            else:
                bands = [(0, WHITE), (90, shot_color(sh))]
            # region left of X shows new shot; bands trail behind X (to its left)
            ys = np.arange(H, dtype=np.float32)[:, None]; xs = np.arange(W, dtype=np.float32)[None, :]
            d = (X + (H - ys) * skew) - xs        # >0 left of edge
            soft = 30 + 90 * math.sin(math.pi * p)  # motion-blur like softness
            def st(e): return np.clip((d - e) / soft + .5, 0, 1)
            out = a * (1 - st(0)[..., None])
            prev = st(0)
            for k, (off, col) in enumerate(bands):
                nxt = st((k + 1) * 120)
                out += col * (prev - nxt)[..., None]
                prev = nxt
            out += b * prev[..., None]
            if both: draw_footer(out)
            return out
    for i in range(len(SHOTS)):
        if SHOTS[i]['start'] <= tg < SHOTS[i]['start'] + SHOTS[i]['dur']: break
    shot_draw(cv, i, tg)
    return cv

def to8(f): return (np.clip(f, 0, 1) * 255 + 0.5).astype(np.uint8)

if __name__ == '__main__':
    mode = sys.argv[1]
    if mode == 'info':
        for s_ in SHOTS: print(f"{s_['start']:7.2f} {s_['dur']:5.1f} {s_['kind']:9s} p{s_.get('page', '')} {s_.get('h', {}).get('name', '') if s_.get('h') else ''}")
        print('TOTAL', TOTAL); sys.exit()
    setup()
    if mode == 'frame':
        os.makedirs(os.path.dirname(sys.argv[2]) or '.', exist_ok=True)
        for tt in sys.argv[3:]:
            Image.fromarray(to8(render(float(tt)))).save(f'{sys.argv[2]}_{float(tt):07.2f}.png')
    elif mode == 'chunk':
        i, n, out = int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
        N = int(round(TOTAL * FPS)); a = N * i // n; b = N * (i + 1) // n
        if len(sys.argv) > 6: a, b = int(sys.argv[5]), int(sys.argv[6])
        enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                                '-c:v', 'libx264', '-preset', 'medium', '-crf', '14', '-maxrate', '60M', '-bufsize', '120M',
                                '-profile:v', 'high', '-level', '5.1', '-pix_fmt', 'yuv420p', '-g', '50', '-keyint_min', '50', '-sc_threshold', '0',
                                '-x264-params', 'threads=2:rc-lookahead=15', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709',
                                '-vf', 'scale=out_color_matrix=bt709:out_range=tv', out], stdin=subprocess.PIPE)
        t0 = time.time()
        for fi in range(a, b):
            enc.stdin.write(to8(render(fi / FPS)).tobytes())
            if (fi - a) % 50 == 0: print(f'chunk {i}: {fi - a}/{b - a} {time.time() - t0:.0f}s', flush=True)
        enc.stdin.close(); enc.wait(); print('done', i, flush=True)
