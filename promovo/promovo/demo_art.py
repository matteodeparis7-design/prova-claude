"""Illustrazioni di prodotti per il volantino dimostrativo (marche inventate, nessun diritto d'autore).

Ogni disegno è fatto con forme semplici, sfumature e ombre, su fondo bianco
(così lo scontorno automatico funziona come con le foto vere).
"""
from __future__ import annotations

import io
import math

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .modules.video.render import font

W, H = 600, 450
SS = 2  # disegno a risoluzione doppia, poi ridotto: bordi morbidi


def _canvas():
    img = Image.new("RGBA", (W * SS, H * SS), (255, 255, 255, 255))
    return img, ImageDraw.Draw(img)


def _f(size, bold=True) -> ImageFont.FreeTypeFont:
    return font(int(size * SS), bold)


def _s(*v):
    return [x * SS for x in v]


def _vgrad(w, h, top, bottom) -> Image.Image:
    g = Image.linear_gradient("L").resize((w, h))
    return Image.composite(Image.new("RGB", (w, h), bottom), Image.new("RGB", (w, h), top), g)


def _hshade(w, h, base, dark=0.35, light=0.25) -> Image.Image:
    """Sfumatura orizzontale che simula un oggetto cilindrico illuminato da sinistra."""
    img = Image.new("RGB", (w, h))
    px = img.load()
    for x in range(w):
        t = x / max(1, w - 1)
        k = 1 + light * math.cos(t * math.pi * 1.2 + 0.4) - dark * t ** 2
        c = tuple(max(0, min(255, int(ch * k))) for ch in base)
        for y in range(h):
            px[x, y] = c
    return img


def _paste_shape(img, shape_img, mask, xy):
    img.paste(shape_img, xy, mask)


def _shadow(img, box, radius=30):
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse(box, fill=(0, 0, 0, 60))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(radius)))


def _label(d, center, text, size, fill, bold=True):
    d.text(center, text, font=_f(size, bold), fill=fill, anchor="mm")


def _finish(img) -> bytes:
    out = img.resize((W, H), Image.LANCZOS).convert("RGB")
    buf = io.BytesIO()
    out.save(buf, format="PNG")
    return buf.getvalue()


def _box(img, d, x0, y0, x1, y1, color, side_color, radius=10):
    """Scatola in prospettiva leggera: fronte + lato."""
    dx = (x1 - x0) * 0.16
    d.polygon(_s(x1, y0, x1 + dx, y0 + 14, x1 + dx, y1 - 10, x1, y1), fill=side_color)
    front = _vgrad((x1 - x0) * SS, (y1 - y0) * SS, color, tuple(int(c * 0.85) for c in color))
    m = Image.new("L", front.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, front.width - 1, front.height - 1), radius=radius * SS, fill=255)
    img.paste(front, (x0 * SS, y0 * SS), m)


def pasta():
    img, d = _canvas()
    _shadow(img, _s(120, 380, 480, 425))
    _box(img, d, 150, 60, 420, 400, (28, 76, 160), (18, 50, 110))
    d.rounded_rectangle(_s(180, 170, 390, 300), radius=18 * SS, fill=(250, 236, 196))
    for i in range(16):
        x = 192 + i * 12
        d.line(_s(x, 182, x + 6, 290), fill=(226, 186, 92), width=4 * SS)
    _label(d, _s(285, 110), "PASTIFICIO", 22, (255, 255, 255))
    _label(d, _s(285, 140), "SOLE", 30, (255, 214, 64))
    _label(d, _s(285, 330), "SPAGHETTI n.5", 24, (255, 255, 255))
    _label(d, _s(285, 365), "500 g", 18, (200, 214, 240), False)
    return _finish(img)


def passata():
    img, d = _canvas()
    _shadow(img, _s(200, 395, 400, 430))
    body = _hshade(150 * SS, 260 * SS, (198, 30, 32))
    m = Image.new("L", body.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, body.width - 1, body.height - 1), radius=40 * SS, fill=255)
    img.paste(body, (225 * SS, 145 * SS), m)
    d.rounded_rectangle(_s(262, 70, 338, 150), radius=14 * SS, fill=(198, 30, 32))
    d.rounded_rectangle(_s(255, 52, 345, 82), radius=8 * SS, fill=(40, 120, 52))
    d.rounded_rectangle(_s(225, 220, 375, 330), radius=6 * SS, fill=(250, 244, 226))
    d.ellipse(_s(270, 228, 330, 270), fill=(214, 40, 36))
    d.polygon(_s(300, 226, 290, 236, 310, 236), fill=(40, 120, 52))
    _label(d, _s(300, 290), "PASSATA", 22, (150, 20, 20))
    _label(d, _s(300, 315), "di pomodoro", 15, (90, 60, 40), False)
    return _finish(img)


def mozzarella():
    img, d = _canvas()
    _shadow(img, _s(140, 380, 460, 420))
    bag = _vgrad(300 * SS, 250 * SS, (236, 244, 252), (196, 214, 236))
    m = Image.new("L", bag.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, bag.width - 1, bag.height - 1), radius=60 * SS, fill=255)
    img.paste(bag, (150 * SS, 130 * SS), m)
    ball = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(ball).ellipse(_s(200, 170, 400, 350), fill=(255, 255, 250, 255))
    img.alpha_composite(ball)
    d.ellipse(_s(230, 190, 300, 240), fill=(255, 255, 255))
    d.rounded_rectangle(_s(170, 300, 430, 360), radius=12 * SS, fill=(24, 110, 70))
    _label(d, _s(300, 330), "FIOR DI LATTE", 22, (255, 255, 255))
    d.polygon(_s(270, 130, 330, 130, 315, 95, 285, 95), fill=(196, 214, 236))
    return _finish(img)


def chicken():
    img, d = _canvas()
    _shadow(img, _s(90, 360, 510, 410))
    d.rounded_rectangle(_s(100, 170, 500, 370), radius=30 * SS, fill=(244, 244, 238))
    d.rounded_rectangle(_s(118, 186, 482, 354), radius=24 * SS, fill=(226, 228, 222))
    for i, (x, y) in enumerate([(150, 205), (240, 215), (330, 205), (190, 270), (300, 275)]):
        meat = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(meat).ellipse(_s(x, y, x + 130, y + 70), fill=(246, 196, 176, 255))
        img.alpha_composite(meat)
        d.arc(_s(x + 15, y + 12, x + 115, y + 58), 200, 340, fill=(232, 168, 150), width=4 * SS)
    d.rounded_rectangle(_s(340, 120, 500, 175), radius=10 * SS, fill=(196, 32, 40))
    _label(d, _s(420, 147), "PETTO DI POLLO", 16, (255, 255, 255))
    return _finish(img)


def oil():
    img, d = _canvas()
    _shadow(img, _s(215, 400, 385, 432))
    body = _hshade(130 * SS, 250 * SS, (46, 92, 40))
    m = Image.new("L", body.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, body.width - 1, body.height - 1), radius=26 * SS, fill=255)
    img.paste(body, (235 * SS, 160 * SS), m)
    d.polygon(_s(250, 165, 350, 165, 322, 95, 278, 95), fill=(46, 92, 40))
    d.rounded_rectangle(_s(276, 50, 324, 100), radius=8 * SS, fill=(176, 140, 60))
    d.rounded_rectangle(_s(245, 230, 355, 350), radius=8 * SS, fill=(244, 230, 186))
    d.ellipse(_s(282, 242, 318, 278), fill=(120, 150, 40))
    _label(d, _s(300, 298), "OLIO EVO", 18, (60, 80, 30))
    _label(d, _s(300, 325), "1 litro", 14, (110, 90, 50), False)
    return _finish(img)


def coffee():
    img, d = _canvas()
    _shadow(img, _s(160, 385, 440, 425))
    _box(img, d, 190, 90, 390, 400, (92, 52, 32), (60, 34, 20), radius=16)
    d.polygon(_s(190, 90, 390, 90, 370, 60, 210, 60), fill=(110, 64, 40))
    d.rounded_rectangle(_s(210, 170, 370, 300), radius=12 * SS, fill=(212, 160, 60))
    d.ellipse(_s(255, 190, 325, 250), fill=(92, 52, 32))
    d.line(_s(290, 195, 290, 245), fill=(212, 160, 60), width=4 * SS)
    _label(d, _s(290, 130), "CAFFÈ", 30, (240, 214, 160))
    _label(d, _s(290, 280), "MACINATO", 17, (60, 34, 20))
    _label(d, _s(290, 345), "250 g", 18, (240, 214, 160), False)
    return _finish(img)


def apples():
    img, d = _canvas()
    _shadow(img, _s(110, 360, 490, 410))
    for (x, y, r) in [(150, 180, 110), (300, 150, 120), (230, 230, 115)]:
        ap = Image.new("RGBA", img.size, (0, 0, 0, 0))
        dd = ImageDraw.Draw(ap)
        dd.ellipse(_s(x, y, x + r * 1.15, y + r), fill=(232, 196, 44, 255))
        dd.ellipse(_s(x + 18, y + 14, x + 52, y + 40), fill=(250, 232, 140, 255))
        img.alpha_composite(ap.filter(ImageFilter.GaussianBlur(0.6 * SS)))
        d.line(_s(x + r * 0.58, y + 8, x + r * 0.62, y - 18), fill=(110, 70, 30), width=5 * SS)
        d.ellipse(_s(x + r * 0.62, y - 22, x + r * 0.62 + 40, y - 2), fill=(70, 150, 60))
    return _finish(img)


def detergent():
    img, d = _canvas()
    _shadow(img, _s(180, 395, 420, 430))
    body = _hshade(200 * SS, 270 * SS, (36, 110, 220))
    m = Image.new("L", body.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, body.width - 1, body.height - 1), radius=40 * SS, fill=255)
    img.paste(body, (200 * SS, 130 * SS), m)
    d.rounded_rectangle(_s(330, 80, 390, 140), radius=12 * SS, fill=(240, 240, 248))
    d.rounded_rectangle(_s(225, 200, 375, 330), radius=20 * SS, fill=(255, 255, 255))
    for i, c in enumerate([(120, 200, 255), (80, 170, 250), (40, 140, 240)]):
        d.ellipse(_s(255 + i * 30, 225, 290 + i * 30, 260), fill=c)
    _label(d, _s(300, 285), "BUCATO", 22, (30, 90, 190))
    _label(d, _s(300, 310), "30 lavaggi", 14, (60, 80, 120), False)
    return _finish(img)


def cookies():
    img, d = _canvas()
    _shadow(img, _s(130, 385, 470, 425))
    bag = _vgrad(300 * SS, 270 * SS, (232, 150, 60), (196, 110, 40))
    m = Image.new("L", bag.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, bag.width - 1, bag.height - 1), radius=26 * SS, fill=255)
    img.paste(bag, (150 * SS, 120 * SS), m)
    for (x, y) in [(190, 230), (290, 215), (240, 290), (340, 290)]:
        d.ellipse(_s(x, y, x + 80, y + 80), fill=(222, 176, 104))
        d.ellipse(_s(x + 8, y + 8, x + 72, y + 72), outline=(196, 146, 80), width=3 * SS)
        for k in range(5):
            a = k * 1.26
            d.ellipse(_s(x + 40 + 20 * math.cos(a) - 4, y + 40 + 20 * math.sin(a) - 4,
                         x + 40 + 20 * math.cos(a) + 4, y + 40 + 20 * math.sin(a) + 4), fill=(170, 120, 60))
    _label(d, _s(300, 165), "FROLLINI", 30, (255, 246, 220))
    return _finish(img)


def water():
    img, d = _canvas()
    _shadow(img, _s(110, 395, 490, 430))
    for i in range(3):
        for row in range(2):
            x = 140 + i * 110 + row * 20
            y = 120 + row * 20
            b = _hshade(90 * SS, 260 * SS, (150, 205, 240))
            m = Image.new("L", b.size, 0)
            ImageDraw.Draw(m).rounded_rectangle((0, 0, b.width - 1, b.height - 1), radius=26 * SS, fill=255)
            img.paste(b, (x * SS, y * SS), m)
            d.rounded_rectangle(_s(x + 30, y - 22, x + 60, y + 4), radius=5 * SS, fill=(30, 110, 200))
            d.rectangle(_s(x, y + 120, x + 90, y + 170), fill=(30, 110, 200))
    _label(d, _s(310, 285), "ACQUA NATURALE", 17, (255, 255, 255))
    return _finish(img)


def ice_cream():
    img, d = _canvas()
    _shadow(img, _s(150, 380, 450, 420))
    d.polygon(_s(170, 180, 430, 180, 405, 390, 195, 390), fill=(252, 240, 214))
    d.rounded_rectangle(_s(160, 150, 440, 195), radius=14 * SS, fill=(150, 90, 180))
    d.ellipse(_s(220, 230, 380, 330), fill=(255, 236, 170))
    d.ellipse(_s(240, 210, 320, 270), fill=(255, 248, 210))
    d.line(_s(300, 300, 330, 250), fill=(110, 70, 40), width=6 * SS)
    _label(d, _s(300, 360), "GELATO VANIGLIA", 18, (120, 70, 150))
    return _finish(img)


def salmon():
    img, d = _canvas()
    _shadow(img, _s(100, 365, 500, 410))
    d.rounded_rectangle(_s(110, 150, 490, 370), radius=24 * SS, fill=(30, 50, 80))
    d.rounded_rectangle(_s(130, 170, 470, 350), radius=18 * SS, fill=(236, 240, 244))
    for i in range(4):
        x = 150 + i * 75
        sl = Image.new("RGBA", img.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(sl)
        sd.ellipse(_s(x, 190, x + 110, 330), fill=(244, 128, 84, 255))
        for k in range(4):
            sd.arc(_s(x + 10, 200 + k * 28, x + 100, 250 + k * 28), 200, 340, fill=(255, 200, 170, 255), width=4 * SS)
        img.alpha_composite(sl)
    d.rounded_rectangle(_s(300, 110, 490, 160), radius=10 * SS, fill=(30, 50, 80))
    _label(d, _s(395, 135), "AFFUMICATO", 18, (255, 255, 255))
    return _finish(img)


ART = {
    "Spaghetti di grano duro": pasta, "Passata di pomodoro": passata, "Mozzarella fior di latte": mozzarella,
    "Petto di pollo a fette": chicken, "Olio extravergine di oliva": oil, "Caffè macinato": coffee,
    "Mele Golden": apples, "Detersivo lavatrice": detergent, "Biscotti frollini": cookies,
    "Acqua naturale": water, "Gelato vaniglia": ice_cream, "Salmone affumicato": salmon,
}


def product_png(name: str) -> bytes | None:
    fn = ART.get(name)
    return fn() if fn else None
