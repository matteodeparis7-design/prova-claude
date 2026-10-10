#!/usr/bin/env python3
"""New 'Essere Decò' loyalty-card presentation (replaces the first 37.76 s of the card spot).
render_essere(t) -> float32 HxWx3.   usage: essere.py <t>...  (test PNGs in testv/)"""
import os, sys, math
import numpy as np, cv2, cairo
from PIL import Image, ImageDraw, ImageFont
import vignettes as V
from vignettes import (W, H, hx, clamp, lerp, prog, e_io3, e_o3, e_o5, e_i3, e_oback, new_surface, surf_rgba, over, blit,
                       add_glow, rrect, lin, rad, load_rgba)

S = V.S
CUT = 945 / 25.0          # original spot resumes (phone animation) at this time
XF = 0.16                 # short crossfade into the original (compositions match)

SLATE_A, SLATE_B = np.array([45, 54, 66], np.float32) / 255, np.array([24, 30, 36], np.float32) / 255
CARD_BLUE = (131, 194, 235); CARD_PAT = (119, 188, 232)
RED = (0.886, 0.137, 0.169); RED8 = (226, 35, 43); NAVY8 = (22, 50, 74)
ORANGE = (1.0, 0.62, 0.23); WHITE = (1, 1, 1)
F = {('J', w): S + f'/fonts/Jost-{w}.ttf' for w in (500, 600, 700, 800, 900)}
F.update({('N', w): S + f'/fonts/Nunito-{w}.ttf' for w in (700, 800, 900)})

def font(fam, w, size): return ImageFont.truetype(F[(fam, w)], size)

def text(txt, size, w=800, color=(255, 255, 255), track=0, fam='J'):
    f = font(fam, w, size)
    ws = [f.getlength(c) for c in txt]; tw = int(sum(ws) + track * (len(txt) - 1)) + 24
    asc, desc = f.getmetrics()
    im = Image.new('RGBA', (tw, asc + desc + 24), (0, 0, 0, 0)); d = ImageDraw.Draw(im); x = 12
    for c, wd in zip(txt, ws): d.text((x, 12), c, font=f, fill=tuple(color) + (255,)); x += wd + track
    im = im.crop(im.getbbox())
    return np.asarray(im, np.float32) / 255

def lines(spec, gap=18):
    """stack text layers vertically, centred: spec = [(layer)], returns one RGBA"""
    w = max(l.shape[1] for l in spec); h = sum(l.shape[0] for l in spec) + gap * (len(spec) - 1)
    out = np.zeros((h, w, 4), np.float32); y = 0
    for l in spec:
        x = (w - l.shape[1]) // 2; out[y:y + l.shape[0], x:x + l.shape[1]] = l; y += l.shape[0] + gap
    return out

def left_lines(spec, gap=18):
    w = max(l.shape[1] for l in spec); h = sum(l.shape[0] for l in spec) + gap * (len(spec) - 1)
    out = np.zeros((h, w, 4), np.float32); y = 0
    for l in spec: out[y:y + l.shape[0], :l.shape[1]] = l; y += l.shape[0] + gap
    return out

def blit_left(dst, rgba, x0, cy, alpha=1.0, scale=1.0):
    blit(dst, rgba, x0 + rgba.shape[1] * scale / 2, cy, alpha, scale)

# ------------------------------------------------------------------ the card (vector-quality bitmap, 2000 px wide)
CW, CH = 2000, int(2000 * 53.98 / 85.6)
def build_card():
    ss = 1
    im = Image.new('RGBA', (CW, CH), (0, 0, 0, 0))
    m = Image.new('L', (CW * 4, CH * 4), 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, CW * 4 - 1, CH * 4 - 1], 110 * 4, fill=255)
    m = m.resize((CW, CH), Image.LANCZOS)
    base = Image.new('RGBA', (CW, CH), CARD_BLUE + (255,)); d = ImageDraw.Draw(base)
    # subtle diagonal sheen in base
    g = np.linspace(0, 1, CW)[None, :] * 0.6 + np.linspace(0, 1, CH)[:, None] * 0.4
    sheen = (np.clip(1 - np.abs(g - 0.35) / 0.35, 0, 1) ** 2 * 18).astype(np.float32)
    arr = np.asarray(base, np.float32); arr[..., :3] = np.clip(arr[..., :3] + sheen[..., None], 0, 255)
    base = Image.fromarray(arr.astype(np.uint8), 'RGBA'); d = ImageDraw.Draw(base)
    # repeating 'essere' pattern
    fp = font('N', 900, 225)
    wword = fp.getlength('essere')
    for r, y in enumerate(range(-90, CH + 60, 205)):
        x = -((r * 397) % int(wword))
        while x < CW:
            d.text((x, y), 'essere', font=fp, fill=CARD_PAT + (255,)); x += wword + 4
    # central white wordmark: 'essere' + Decò mark
    fw = font('N', 800, 300)
    deco = Image.open(S + '/essere/deco_white.png'); dh = 560; deco = deco.resize((int(deco.width * dh / deco.height), dh), Image.LANCZOS)
    tw = fw.getlength('essere'); total = tw + 40 + deco.width * 0.93
    x0 = (CW - total) / 2 - 20; yb = CH * 0.47
    bb = fw.getbbox('essere')
    # soft shadow for legibility
    sh = Image.new('L', (CW, CH), 0); ImageDraw.Draw(sh).text((x0 + 6, yb - (bb[3] - bb[1]) / 2 - bb[1] + 10), 'essere', font=fw, fill=90)
    base.paste((70, 140, 190, 255), (0, 0), Image.fromarray(cv2.GaussianBlur(np.asarray(sh), (0, 0), 10)))
    d.text((x0, yb - (bb[3] - bb[1]) / 2 - bb[1]), 'essere', font=fw, fill=(255, 255, 255, 255))
    base.alpha_composite(deco, (int(x0 + tw + 30 - deco.width * 0.07), int(yb - dh * 0.53)))
    # social icons bottom-left
    r = 46; cy = CH - 120
    for k, kind in enumerate(('f', 'ig', 'yt')):
        cx = 150 + k * 125
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(255, 255, 255, 255), width=9)
        if kind == 'f':
            ff = font('N', 900, 74); b2 = ff.getbbox('f'); d.text((cx - (b2[2] + b2[0]) / 2, cy - (b2[3] + b2[1]) / 2), 'f', font=ff, fill=(255, 255, 255, 255))
        elif kind == 'ig':
            d.rounded_rectangle([cx - 24, cy - 24, cx + 24, cy + 24], 12, outline=(255, 255, 255, 255), width=7)
            d.ellipse([cx - 11, cy - 11, cx + 11, cy + 11], outline=(255, 255, 255, 255), width=6); d.ellipse([cx + 12, cy - 19, cx + 18, cy - 13], fill=(255, 255, 255, 255))
        else:
            d.rounded_rectangle([cx - 27, cy - 18, cx + 27, cy + 18], 9, fill=(255, 255, 255, 255))
            d.polygon([(cx - 7, cy - 10), (cx - 7, cy + 10), (cx + 11, cy)], fill=CARD_BLUE + (255,))
    # bevel edge highlight
    edge = Image.new('L', (CW * 2, CH * 2), 0); ImageDraw.Draw(edge).rounded_rectangle([3, 3, CW * 2 - 4, CH * 2 - 4], 220, outline=255, width=8)
    edge = edge.resize((CW, CH), Image.LANCZOS)
    base.paste((255, 255, 255, 255), (0, 0), edge.point(lambda v: v * 0.45))
    base.putalpha(m)
    return np.asarray(base, np.float32) / 255

class Card:
    def __init__(self):
        rgba = build_card()
        pm = rgba.copy(); pm[..., :3] *= pm[..., 3:4]
        self.levels = [pm]
        while self.levels[-1].shape[1] > 300:
            l = self.levels[-1]; self.levels.append(cv2.resize(l, (l.shape[1] // 2, l.shape[0] // 2), interpolation=cv2.INTER_AREA))
        # back side: plain blue with magstripe-like band + small logo
        back = np.zeros_like(rgba); back[...] = rgba
        back[..., :3] = np.array(CARD_PAT) / 255
        back[int(CH * 0.14):int(CH * 0.30), :, :3] = np.array([30, 45, 60]) / 255
        bm = back.copy(); bm[..., :3] *= bm[..., 3:4]
        self.back = [bm]
        while self.back[-1].shape[1] > 300:
            l = self.back[-1]; self.back.append(cv2.resize(l, (l.shape[1] // 2, l.shape[0] // 2), interpolation=cv2.INTER_AREA))

    def quad(self, cx, cy, w, roty=0.0, rotz=0.0, rotx=0.0, f=4200):
        h = w * CH / CW; pts = []
        cz, sz = math.cos(rotz), math.sin(rotz); cyy, syy = math.cos(roty), math.sin(roty); cxx, sxx = math.cos(rotx), math.sin(rotx)
        for (X, Y) in [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]:
            x, y, z = X, Y, 0.0
            x, z = x * cyy, x * syy                     # rot Y
            y, z = y * cxx - z * sxx, y * sxx + z * cxx  # rot X
            x, y = x * cz - y * sz, x * sz + y * cz      # rot Z
            p = f / (f + z); pts.append((cx + x * p, cy + y * p))
        return np.array(pts, np.float32)

    def draw(self, dst, cx, cy, w, roty=0.0, rotz=0.0, rotx=0.0, alpha=1.0, shadow=0.55, glint=-1.0):
        if alpha <= 0 or w < 4: return
        q = self.quad(cx, cy, w, roty, rotz, rotx)
        front = math.cos(roty) * math.cos(rotx) >= 0
        lv = self.levels if front else self.back
        # area-based level choice
        wproj = max(np.linalg.norm(q[1] - q[0]), 1)
        L = 0
        while L + 1 < len(lv) and lv[L + 1].shape[1] >= wproj: L += 1
        src = lv[L]; sh_, sw_ = src.shape[:2]
        sq = np.array([[0, 0], [sw_, 0], [sw_, sh_], [0, sh_]], np.float32)
        if not front: sq = sq[[1, 0, 3, 2]]
        # shadow
        if shadow > 0:
            X0, Y0 = int(max(0, q[:, 0].min() - 300)), int(max(0, q[:, 1].min() - 200))
            X1, Y1 = int(min(W, q[:, 0].max() + 300)), int(min(H, q[:, 1].max() + 400))
            if X1 > X0 and Y1 > Y0:
                small = 4
                qs = (q + np.array([30, 70], np.float32) - np.array([X0, Y0], np.float32)) / small
                m = np.zeros(((Y1 - Y0) // small + 1, (X1 - X0) // small + 1), np.float32)
                cv2.fillConvexPoly(m, np.round(qs * 16).astype(np.int32), 1.0, lineType=cv2.LINE_AA, shift=4)
                m = cv2.GaussianBlur(m, (0, 0), 45 / small)
                m = cv2.resize(m, (X1 - X0, Y1 - Y0))[..., None] * shadow * alpha
                roi = dst[Y0:Y1, X0:X1]; roi *= 1 - m
        X0, Y0 = int(max(0, q[:, 0].min() - 2)), int(max(0, q[:, 1].min() - 2))
        X1, Y1 = int(min(W, q[:, 0].max() + 3)), int(min(H, q[:, 1].max() + 3))
        if X1 <= X0 or Y1 <= Y0: return
        Hm = cv2.getPerspectiveTransform(sq, q - np.array([X0, Y0], np.float32))
        out = cv2.warpPerspective(src, Hm, (X1 - X0, Y1 - Y0), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
        if 0 <= glint <= 1:
            yy, xx = np.mgrid[0:Y1 - Y0, 0:X1 - X0].astype(np.float32)
            span = (X1 - X0) + (Y1 - Y0)
            pos = lerp(-0.25 * span, 1.25 * span, e_io3(glint))
            band = np.exp(-(((xx + yy * 0.55) - pos) / (0.06 * span)) ** 2) * 0.55
            out[..., :3] += (out[..., 3] * band)[..., None] * (1 - out[..., :3])
        roi = dst[Y0:Y1, X0:X1]; a = out[..., 3:4] * alpha
        roi *= 1 - a; roi += out[..., :3] * alpha

# ------------------------------------------------------------------ drawn props
def coin_layer(r):
    s, c = new_surface(int(r * 2.4), int(r * 2.4)); cx = cy = r * 1.2
    c.arc(cx, cy, r, 0, 2 * math.pi); rad(c, cx - r * 0.3, cy - r * 0.3, 0, r * 1.3, [(0, hx('fff2b0')), (0.5, hx('f2c032')), (1, hx('b67d0c'))]); c.fill()
    c.arc(cx, cy, r * 0.80, 0, 2 * math.pi); c.set_source_rgba(*hx('a86f08', 0.9)); c.set_line_width(r * 0.06); c.stroke()
    c.select_font_face('Jost', cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD); c.set_font_size(r * 1.05)
    ext = c.text_extents('€'); c.move_to(cx - ext.width / 2 - ext.x_bearing, cy - ext.height / 2 - ext.y_bearing)
    c.set_source_rgba(*hx('9a6206')); c.show_text('€')
    c.arc(cx - r * 0.35, cy - r * 0.45, r * 0.22, 0, 2 * math.pi); c.set_source_rgba(1, 1, 1, 0.45); c.fill()
    a = surf_rgba(s); st = a.copy(); st[..., :3] = np.where(a[..., 3:4] > 0, a[..., :3] / np.maximum(a[..., 3:4], 1e-4), 0)
    return st

def gift_layer(sz, lid_open=0.0):
    s, c = new_surface(int(sz * 1.8), int(sz * 1.9)); ox, oy = sz * 0.4, sz * 0.75
    w, h = sz, sz * 0.78
    # box
    rrect(c, ox, oy, w, h, sz * 0.05); lin(c, ox, 0, ox + w, 0, [(0, hx('e2232b')), (0.6, hx('c81a22')), (1, hx('9c1118'))]); c.fill()
    c.rectangle(ox + w * 0.42, oy, w * 0.16, h); c.set_source_rgba(1, 1, 1, 1); c.fill()
    # lid
    c.save(); c.translate(ox + w * 0.02 + w * 0.5, oy - lid_open * sz * 0.42); c.rotate(-0.18 * lid_open); c.translate(-w * 0.5, 0)
    rrect(c, -w * 0.06, -h * 0.26, w * 1.08, h * 0.28, sz * 0.04); lin(c, 0, -h * 0.26, 0, 0, [(0, hx('f0343c')), (1, hx('c81a22'))]); c.fill()
    c.rectangle(w * 0.42 - w * 0.02, -h * 0.26, w * 0.16, h * 0.28); c.set_source_rgba(1, 1, 1, 1); c.fill()
    # bow
    for sg in (-1, 1):
        c.save(); c.translate(w * 0.5, -h * 0.26); c.scale(sg, 1)
        c.move_to(0, 0); c.curve_to(w * 0.05, -h * 0.35, w * 0.38, -h * 0.30, w * 0.25, -h * 0.02); c.close_path()
        c.set_source_rgba(1, 1, 1, 1); c.fill_preserve(); c.set_source_rgba(0.8, 0.85, 0.9, 1); c.set_line_width(4); c.stroke(); c.restore()
    c.restore()
    a = surf_rgba(s); st = a.copy(); st[..., :3] = np.where(a[..., 3:4] > 0, a[..., :3] / np.maximum(a[..., 3:4], 1e-4), 0)
    return st

def icon_tile(kind, size=230):
    s, c = new_surface(size, size); r = size / 2
    c.arc(r, r, r - 4, 0, 2 * math.pi); c.set_source_rgba(1, 1, 1, 1); c.fill()
    c.set_source_rgba(*RED, 1); c.set_line_width(size * 0.055); c.set_line_cap(cairo.LINE_CAP_ROUND); c.set_line_join(cairo.LINE_JOIN_ROUND)
    if kind == 'free':      # price tag with 0 €
        c.save(); c.translate(r, r); c.rotate(-0.6)
        c.move_to(-size * 0.26, -size * 0.13); c.line_to(size * 0.12, -size * 0.13); c.line_to(size * 0.27, 0); c.line_to(size * 0.12, size * 0.13); c.line_to(-size * 0.26, size * 0.13); c.close_path(); c.stroke()
        c.arc(size * 0.13, 0, size * 0.03, 0, 2 * math.pi); c.fill()
        c.select_font_face('Jost', cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD); c.set_font_size(size * 0.17)
        e = c.text_extents('0€'); c.move_to(-size * 0.07 - e.width / 2 - e.x_bearing, -e.height / 2 - e.y_bearing); c.show_text('0€'); c.restore()
    elif kind == 'user':
        c.arc(r, r * 0.78, size * 0.13, 0, 2 * math.pi); c.stroke()
        c.arc(r, r * 1.62, size * 0.27, math.pi * 1.12, math.pi * 1.88); c.stroke()
    elif kind == 'web':
        c.rectangle(size * 0.22, size * 0.28, size * 0.56, size * 0.38); c.stroke()
        c.move_to(size * 0.38, size * 0.74); c.line_to(size * 0.62, size * 0.74); c.stroke()
        c.move_to(r, size * 0.66); c.line_to(r, size * 0.74); c.stroke()
        c.move_to(size * 0.32, size * 0.52); c.line_to(size * 0.42, size * 0.44); c.line_to(size * 0.52, size * 0.50); c.line_to(size * 0.66, size * 0.38); c.stroke()
    a = surf_rgba(s); st = a.copy(); st[..., :3] = np.where(a[..., 3:4] > 0, a[..., :3] / np.maximum(a[..., 3:4], 1e-4), 0)
    return st

def pill(w, h, col, r=None):
    s, c = new_surface(int(w), int(h)); rrect(c, 0, 0, w, h, r if r is not None else h / 2); c.set_source_rgba(*col, 1); c.fill()
    a = surf_rgba(s); st = a.copy(); st[..., :3] = np.where(a[..., 3:4] > 0, a[..., :3] / np.maximum(a[..., 3:4], 1e-4), 0)
    return st

def product_tile(x, name1, name2, ip, cp):
    """white rounded tile with cutout product + flyer-style blue 'con carta' price tag"""
    tw, th = 960, 1080
    tile = Image.new('RGBA', (tw, th), (0, 0, 0, 0)); d = ImageDraw.Draw(tile)
    m = Image.new('L', (tw * 2, th * 2), 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, tw * 2 - 1, th * 2 - 1], 120, fill=255)
    tile.paste((255, 255, 255, 255), (0, 0), m.resize((tw, th), Image.LANCZOS))
    p = Image.open(S + f'/cut/x{x}.png'); sc = min(700 / p.width, 520 / p.height); p = p.resize((int(p.width * sc), int(p.height * sc)), Image.LANCZOS)
    tile.alpha_composite(p, ((tw - p.width) // 2, 60 + (540 - p.height) // 2))
    f1 = font('J', 800, 64); f2 = font('J', 600, 50)
    for k, (t, f, col) in enumerate(((name1, f1, NAVY8), (name2, f2, (60, 80, 100)))):
        b = f.getbbox(t); d.text(((tw - (b[2] - b[0])) / 2 - b[0], 630 + k * 78 - b[1]), t, font=f, fill=col)
    # price tag (light blue like the flyer)
    tagw, tagh = 560, 220; tx0 = (tw - tagw) // 2; ty0 = 800
    d.rounded_rectangle([tx0, ty0, tx0 + tagw, ty0 + tagh], 40, fill=(142, 200, 238, 255))
    fi, fc, fe = font('J', 900, 190), font('J', 900, 96), font('J', 800, 56)
    bi = fi.getbbox(ip); bc = fc.getbbox(cp); bco = fi.getbbox(',')
    wi = bi[2] - bi[0]; wc = bc[2] - bc[0]; wco = bco[2] - bco[0]
    totw = wi + 2 + wco * 0.45 + wc; x = tx0 + (tagw - totw) / 2; base_y = ty0 + 22
    d.text((x - bi[0], base_y - bi[1]), ip, font=fi, fill=NAVY8)
    xc = x + wi + 2; d.text((xc - bco[0], base_y - bi[1]), ',', font=fi, fill=NAVY8)
    x3 = xc + wco * 0.45; d.text((x3 - bc[0], base_y - bc[1] + 4), cp, font=fc, fill=NAVY8)
    be = fe.getbbox('€'); d.text((x3 + (wc - (be[2] - be[0])) / 2 - be[0], base_y + (bc[3] - bc[1]) + 14 - be[1]), '€', font=fe, fill=NAVY8)
    # 'con carta essere decò' strip
    fs = font('J', 700, 40); t = 'CON CARTA ESSERE DECÒ'; b = fs.getbbox(t); sw = b[2] - b[0] + 60
    d.rounded_rectangle([(tw - sw) / 2, ty0 + tagh - 30, (tw + sw) / 2, ty0 + tagh + 40], 22, fill=RED8 + (255,))
    d.text(((tw - (b[2] - b[0])) / 2 - b[0], ty0 + tagh + 5 - (b[3] - b[1]) / 2 - b[1]), t, font=fs, fill=(255, 255, 255))
    out = np.zeros((th + 60, tw, 4), np.uint8); out[:th] = np.asarray(tile)
    im = Image.fromarray(out, 'RGBA'); im = im.crop(im.getbbox())
    return np.asarray(im, np.float32) / 255

# ------------------------------------------------------------------ assets
class A_: pass
AS = A_()
def assets():
    if hasattr(AS, 'ok'): return
    V.assets(); AS.ok = True
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    u = np.clip(xx / W * 0.55 + yy / H * 0.45, 0, 1)[..., None]
    bg = SLATE_A * (1 - u) + SLATE_B * u
    d = np.exp(-((xx - W * 0.42) ** 2 + (yy - H * 0.45) ** 2) / (2 * 1500 ** 2))[..., None]
    bg = bg * (1 - 0.18 * d) + np.array([0.33, 0.42, 0.52], np.float32) * 0.18 * d
    bg += (np.random.default_rng(5).random((H, W, 1), np.float32) - .5) / 255 * 1.5
    AS.bg = np.clip(bg, 0, 1)
    rbg = np.array([0.80, 0.09, 0.13], np.float32) * (1 - u) + np.array([0.58, 0.04, 0.08], np.float32) * u
    AS.redbg = np.clip(rbg + (np.random.default_rng(6).random((H, W, 1), np.float32) - .5) / 255 * 1.5, 0, 1)
    AS.card = Card()
    AS.coin = coin_layer(95)
    WH = (255, 255, 255)
    AS.t1a = text('LA TUA CARTA FEDELTÀ', 76, 700, (169, 211, 240), 20)
    AS.t1b = text('ESSERE DECÒ', 230, 900, WH, 6)
    AS.t1c = text('PIÙ LA USI, PIÙ RISPARMI!', 70, 800, WH, 6)
    AS.t2 = left_lines([text('OGNI', 96, 700, (169, 211, 240), 14), text('1 € DI SPESA', 190, 900, WH, 3),
                        text('VALE 1 PUNTO', 190, 900, (255, 92, 98), 3)], 26)
    AS.t2pts = text('SALDO PUNTI', 54, 700, (169, 211, 240), 12)
    AS.digits = {ch: text(ch, 150, 900, WH, 0) for ch in '0123456789'}
    AS.t3 = left_lines([text('ACCUMULA PUNTI', 150, 900, WH, 3), text('E TRASFORMALI IN', 110, 700, (169, 211, 240), 6),
                        text('SCONTI E PREMI', 170, 900, (255, 92, 98), 3), text('riservati solo a te', 72, 600, WH, 2)], 26)
    AS.gift = [gift_layer(420, k / 10) for k in range(11)]
    AS.t4a = text('PREZZI SPECIALI', 170, 900, WH, 4)
    AS.t4b = text('CON LA CARTA ESSERE DECÒ', 78, 700, (169, 211, 240), 12)
    AS.tiles = [product_tile(226, 'AIA NUGGETS', 'DI POLLO 240 G', '2', '49'),
                product_tile(223, 'OROGEL TANTO CUORE', 'CARCIOFI 300 G', '2', '19'),
                product_tile(220, 'FINDUS FILETTI', 'DI PLATESSA 250 G', '5', '19')]
    AS.t5 = text('LA CARTA CHE TI PREMIA', 150, 900, WH, 4)
    AS.feat = [(icon_tile('free'), text('È GRATUITA', 84, 900, WH, 4), text('nessun costo, mai', 54, 600, (169, 211, 240), 2)),
               (icon_tile('user'), text('È PERSONALE', 84, 900, WH, 4), text('i tuoi punti, i tuoi premi', 54, 600, (169, 211, 240), 2)),
               (icon_tile('web'), text('SALDO PUNTI', 84, 900, WH, 4), text('su supermercatideco.it', 54, 600, (169, 211, 240), 2))]
    AS.t6 = left_lines([text('NON HAI ANCORA', 150, 900, WH, 3), text('LA CARTA', 210, 900, WH, 3), text('ESSERE DECÒ?', 150, 900, (255, 214, 214), 3)], 22)
    AS.t6b = left_lines([text('Richiedila subito al box informazioni', 64, 600, WH, 1), text('del punto vendita o su supermercatideco.it', 64, 600, WH, 1)], 14)
    AS.t6c = text('È GRATIS!', 84, 900, RED8, 6)

# ------------------------------------------------------------------ helpers
def deco_dots(img, t, out=0.0, red_xy=(3420, 300), white_xy=(3650, 2010), orange_xy=(170, 1560)):
    a = 1 - out
    pr = e_oback(prog(t, 0.0, 0.7), 1.3); pw = e_oback(prog(t, 0.15, 0.7), 1.3); po = e_oback(prog(t, 0.3, 0.6), 1.6)
    fl = lambda k: 18 * math.sin(t * 0.8 + k)
    s, c = new_surface()
    if pr > 0: c.arc(red_xy[0], red_xy[1] + fl(0), 260 * pr, 0, 2 * math.pi); c.set_source_rgba(*RED, a); c.fill()
    if pw > 0: c.arc(white_xy[0] + fl(1), white_xy[1], 190 * pw, 0, 2 * math.pi); c.set_source_rgba(1, 1, 1, a); c.fill()
    if po > 0: c.arc(orange_xy[0], orange_xy[1] + fl(2), 46 * po, 0, 2 * math.pi); c.set_source_rgba(*ORANGE, a); c.fill()
    over(img, surf_rgba(s))

def rise(img, layer, x0, cy, t, t0, dur=0.7, t_out=None, left=True, scale=1.0):
    p = e_o5(prog(t, t0, dur)); q = e_i3(prog(t, t_out, 0.4)) if t_out is not None else 0
    a = p * (1 - q)
    if a <= 0: return
    dy = (1 - p) * 70 - q * 40
    if left: blit_left(img, layer, x0, cy + dy, a, scale)
    else: blit(img, layer, x0, cy + dy, a, scale)

def number_layer(n):
    s = f'{n:03d}'; ls = [AS.digits[ch] for ch in s]
    w = sum(l.shape[1] for l in ls) + 16 * (len(ls) - 1); h = max(l.shape[0] for l in ls)
    out = np.zeros((h, w, 4), np.float32); x = 0
    for l in ls: out[h - l.shape[0]:, x:x + l.shape[1]] = l; x += l.shape[1] + 16
    return out

# ------------------------------------------------------------------ scenes
S1, S2, S3, S4, S5, S6 = 0.0, 6.0, 12.5, 19.0, 25.5, 31.5
CARD_HOME = (1920, 1170, 1460)        # centre x, y, width
CARD_LEFT = (1180, 1080, 1380)

def card_state(t):
    """returns cx, cy, w, roty, rotz, rotx, alpha, glint"""
    # S1 fly-in
    p = e_o5(prog(t, 0.25, 1.6))
    cx, cy, w = lerp(2700, CARD_HOME[0], p), lerp(-500, CARD_HOME[1], p), lerp(500, CARD_HOME[2], p)
    roty = lerp(-math.pi * 2.0, 0, p); rotz = lerp(-0.6, -0.05, p); rotx = lerp(0.5, 0, p)
    glint = prog(t, 1.9, 1.1) if t < 3.0 else (prog(t, S3 + 0.4, 1.0) if S3 < t < S3 + 1.5 else -1)
    # gentle float
    fl = math.sin(t * 1.3) * 0.035
    # S2 to left
    q = e_io3(prog(t, S2 - 0.3, 1.0))
    cx, cy, w = lerp(cx, CARD_LEFT[0], q), lerp(cy, CARD_LEFT[1], q), lerp(w, CARD_LEFT[2], q)
    rotz = lerp(rotz, -0.10, q); roty += 0.22 * q
    # S4: card flies to top-left corner, small
    r = e_io3(prog(t, S4 - 0.4, 0.9))
    cx, cy, w = lerp(cx, 540, r), lerp(cy, 330, r), lerp(w, 560, r); rotz = lerp(rotz, -0.12, r); roty = lerp(roty, 0.0, r)
    # S5: card hides (slides off left) ; S6: card returns big on red panel
    s = e_io3(prog(t, S5 - 0.4, 0.7))
    cx = lerp(cx, -700, s)
    u = e_o5(prog(t, S6 + 0.2, 1.1))
    if u > 0:
        cx, cy, w = lerp(-900, 2850, u), lerp(1500, 1080, u), lerp(900, 1500, u); rotz = lerp(-0.7, -0.16, u); roty = lerp(1.6, 0.25, u)
        glint = prog(t, S6 + 1.4, 1.0)
    return cx, cy, w, roty + fl, rotz, 0.0 if u > 0 else rotx, 1.0, glint

COINS = [(S2 + 0.9 + 0.32 * k, 900 + 140 * ((k * 3) % 5)) for k in range(7)]

def render_essere(t):
    assets()
    if t >= S6:
        img = AS.redbg.copy()
        pin = e_io3(prog(t, S6 - 0.2, 0.7))
        if pin < 1:
            img = AS.bg.copy(); x = int(W * (1 - pin))
            img[:, x:] = AS.redbg[:, x:]
    else:
        img = AS.bg.copy()
    tl = t
    # decorative dots (first 31 s); fade out before red panel
    if t < S6 + 0.2:
        deco_dots(img, t, out=e_i3(prog(t, S6 - 0.4, 0.4)))
    # ---------- S1 titles
    rise(img, AS.t1a, W / 2, 230, t, 1.6, t_out=S2 - 0.5, left=False)
    rise(img, AS.t1b, W / 2, 420, t, 1.8, t_out=S2 - 0.5, left=False)
    pp = e_oback(prog(t, 2.6, 0.6), 1.5) * (1 - e_i3(prog(t, S2 - 0.5, 0.4)))
    if pp > 0:
        pw = AS.t1c.shape[1] + 140
        if not hasattr(AS, 'pill1'): AS.pill1 = pill(pw, 130, RED)
        blit(img, AS.pill1, W / 2, 1985, min(1, pp * 2), max(0.01, pp))
        blit(img, AS.t1c, W / 2, 1985, clamp(pp * 2 - 0.6))
    # ---------- S2: coins + counter
    rise(img, AS.t2, 2250, 900, t, S2 + 0.4, t_out=S3 - 0.5)
    for (t0, xo) in COINS:
        dt = t - t0
        if 0 <= dt < 0.75:
            k = dt / 0.75; y = lerp(-150, CARD_LEFT[1] - 120, k * k); x = lerp(CARD_LEFT[0] - 300 + xo * 0.4, CARD_LEFT[0], k)
            blit(img, AS.coin, x, y, 1.0 - max(0, (k - 0.85) / 0.15), lerp(1.1, 0.55, k))
    # card on top of coins
    cx, cy, w, ry, rz, rx, ca, gl = card_state(t)
    if t < S6:
        AS.card.draw(img, cx, cy, w, ry, rz, rx, ca, glint=gl)
    # coin sparkles when absorbed
    for (t0, _) in COINS:
        dt = t - t0 - 0.72
        if 0 <= dt < 0.35: add_glow(img, CARD_LEFT[0] + 60, CARD_LEFT[1] - 280, 90, (1, 0.9, 0.5), 0.7 * (1 - dt / 0.35))
    if S2 + 0.8 < t < S3 - 0.2:
        pa = e_o5(prog(t, S2 + 0.8, 0.5)) * (1 - e_i3(prog(t, S3 - 0.6, 0.4)))
        n = 0
        for (t0, _) in COINS:
            if t >= t0 + 0.72: n += 25
        if not hasattr(AS, 'cnt_pill'): AS.cnt_pill = pill(900, 180, (0.09, 0.12, 0.15))
        blit(img, AS.cnt_pill, CARD_LEFT[0], 1840, pa)
        blit_left(img, AS.t2pts, CARD_LEFT[0] - 380, 1840, pa)
        bump = 1 + 0.12 * max([0] + [max(0, 1 - (t - t0 - 0.72) / 0.25) for (t0, _) in COINS if t >= t0 + 0.72])
        blit(img, number_layer(n), CARD_LEFT[0] + 250, 1838, pa, 0.75 * bump)
    # ---------- S3: points -> discounts & prizes, gift box
    rise(img, AS.t3, 2250, 1000, t, S3 + 0.3, t_out=S4 - 0.6)
    gp = e_oback(prog(t, S3 + 0.9, 0.7), 1.4) * (1 - e_i3(prog(t, S4 - 0.6, 0.4)))
    if gp > 0:
        lid = e_io3(prog(t, S3 + 1.8, 0.5)); g = AS.gift[int(round(lid * 10))]
        gx, gy = 2650, 1720 + 8 * math.sin(t * 2)
        blit(img, g, gx, gy - (1 - gp) * 200, min(1, gp * 1.5), max(0.05, gp * 1.0))
        # confetti burst
        ct = t - (S3 + 1.9)
        if 0 < ct < 2.2:
            rr = np.random.default_rng(3); s_, c_ = new_surface()
            for k in range(70):
                ang = rr.uniform(-math.pi * 0.95, -math.pi * 0.05); spd = rr.uniform(700, 1700)
                x = gx + math.cos(ang) * spd * ct; y = gy - 330 + math.sin(ang) * spd * ct + 0.5 * 1500 * ct * ct
                col = [RED, WHITE, ORANGE, (0.51, 0.76, 0.92)][k % 4]
                c_.save(); c_.translate(x, y); c_.rotate(ct * rr.uniform(-8, 8)); c_.rectangle(-14, -7, 28, 14)
                c_.set_source_rgba(*col, clamp(1 - ct / 2.2) * gp); c_.fill(); c_.restore()
            over(img, surf_rgba(s_))
    # ---------- S4: special prices with the card (real flyer products)
    rise(img, AS.t4a, 2150, 300, t, S4 + 0.2, t_out=S5 - 0.5, left=False)
    rise(img, AS.t4b, 2150, 470, t, S4 + 0.35, t_out=S5 - 0.5, left=False)
    for k, tile in enumerate(AS.tiles):
        p = e_oback(prog(t, S4 + 0.6 + 0.25 * k, 0.7), 1.2); q = e_i3(prog(t, S5 - 0.6 + 0.08 * k, 0.45))
        a = clamp(p * 2) * (1 - q)
        if a <= 0: continue
        x = 820 + k * 1100; y = 1330 + (1 - p) * 260 - q * 120
        blit(img, tile, x, y, a, 0.86 * (0.9 + 0.1 * p))
    # ---------- S5: features
    rise(img, AS.t5, W / 2, 470, t, S5 + 0.2, t_out=S6 - 0.4, left=False)
    for k, (ic, ti, su) in enumerate(AS.feat):
        x = 820 + k * 1100
        p = e_oback(prog(t, S5 + 0.6 + 0.3 * k, 0.6), 1.6); q = e_i3(prog(t, S6 - 0.5, 0.4))
        if p <= 0: continue
        blit(img, ic, x, 1080, clamp(p * 2) * (1 - q), max(0.05, p) * 1.6)
        rise(img, ti, x, 1460, t, S5 + 0.85 + 0.3 * k, t_out=S6 - 0.5, left=False)
        rise(img, su, x, 1580, t, S5 + 1.0 + 0.3 * k, t_out=S6 - 0.5, left=False)
    # ---------- S6: request it
    if t >= S6:
        rise(img, AS.t6, 300, 860, t, S6 + 0.5)
        rise(img, AS.t6b, 300, 1440, t, S6 + 1.0)
        pp = e_oback(prog(t, S6 + 1.4, 0.6), 1.5)
        if pp > 0:
            if not hasattr(AS, 'pill6'): AS.pill6 = pill(AS.t6c.shape[1] + 120, 140, WHITE)
            blit(img, AS.pill6, 300 + (AS.t6c.shape[1] + 120) / 2, 1700, min(1, pp * 2), max(0.01, pp))
            blit(img, AS.t6c, 300 + (AS.t6c.shape[1] + 120) / 2, 1700, clamp(pp * 2 - 0.6))
        # card on top of red panel
        cx, cy, w, ry, rz, rx, ca, gl = card_state(t)
        AS.card.draw(img, cx, cy, w, ry, rz, rx, ca, shadow=0.45, glint=gl)
        # red panel slides up revealing the opening composition of the phone animation
        p = prog(t, CUT - 0.80, 0.80)
        if p > 0:
            off = int(round(H * (p ** 2.2)))
            under = AS.bg.copy(); end_dots(under)
            if off < H:
                under[:H - off] = img[off:]
            img = under
    return np.clip(img, 0, 1)

def end_dots(img):
    s, c = new_surface()
    c.arc(1056, 1822, 92, 0, 2 * math.pi); c.set_source_rgba(*ORANGE, 1); c.fill()
    c.arc(1477, 1820, 402, 0, 2 * math.pi); c.set_source_rgba(1, 1, 1, 1); c.fill()
    c.arc(2664, 118, 224, 0, 2 * math.pi); c.set_source_rgba(0.76, 0.12, 0.15, 1); c.fill()
    over(img, surf_rgba(s))

if __name__ == '__main__':
    os.makedirs(S + '/testv', exist_ok=True)
    for tt in sys.argv[1:]:
        im = render_essere(float(tt))
        Image.fromarray((im * 255 + .5).astype(np.uint8)).save(f'{S}/testv/ess_{float(tt):05.2f}.png')
