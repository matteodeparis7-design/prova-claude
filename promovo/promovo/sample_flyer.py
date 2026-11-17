"""Generatore di un volantino PDF di prova (per test e dimostrazioni).

Crea pagine con riquadri prodotto: foto (immagine), nome, formato, prezzo,
prezzo barrato e sconto, come in un volantino vero.
"""
from __future__ import annotations

import io
from dataclasses import dataclass

import pymupdf
from PIL import Image, ImageDraw

from .money import price_parts


@dataclass
class SampleProduct:
    name: str
    size: str
    price_cents: int
    old_price_cents: int | None
    color: tuple[int, int, int]


DEFAULT_PRODUCTS = [
    SampleProduct("Spaghetti di grano duro", "500 g", 79, 129, (230, 190, 90)),
    SampleProduct("Passata di pomodoro", "700 g", 99, 149, (200, 40, 40)),
    SampleProduct("Mozzarella fior di latte", "125 g", 89, None, (240, 240, 235)),
    SampleProduct("Petto di pollo a fette", "al kg", 799, 1090, (240, 200, 170)),
    SampleProduct("Olio extravergine di oliva", "1 litro", 699, 899, (120, 150, 40)),
    SampleProduct("Caffè macinato", "250 g", 249, 349, (90, 60, 40)),
    SampleProduct("Mele Golden", "al kg", 149, None, (230, 210, 60)),
    SampleProduct("Detersivo lavatrice", "30 lavaggi", 399, 650, (60, 120, 220)),
    SampleProduct("Biscotti frollini", "350 g", 129, 199, (210, 160, 90)),
    SampleProduct("Acqua naturale", "6 x 1,5 L", 189, 249, (150, 200, 240)),
    SampleProduct("Gelato vaniglia", "500 g", 299, 399, (250, 240, 200)),
    SampleProduct("Salmone affumicato", "100 g", 349, 499, (240, 140, 100)),
]


def _photo(color: tuple[int, int, int]) -> bytes:
    img = Image.new("RGB", (400, 300), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((40, 30, 360, 270), radius=40, fill=color, outline=(60, 60, 60), width=4)
    d.ellipse((140, 90, 260, 210), fill=tuple(max(0, c - 50) for c in color))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def build_sample_flyer(products: list[SampleProduct] | None = None, per_page: int = 6,
                       validity: str = "Offerte valide dal 13 al 22 novembre 2026",
                       banner: str = "SUPERSTORE") -> bytes:
    products = products or DEFAULT_PRODUCTS
    doc = pymupdf.open()
    W, H = 595, 842  # A4 in punti
    cols, rows = 2, 3
    for start in range(0, len(products), per_page):
        page = doc.new_page(width=W, height=H)
        page.draw_rect(pymupdf.Rect(0, 0, W, 90), color=None, fill=(0.84, 0.15, 0.18))
        page.insert_text((30, 50), banner, fontsize=30, fontname="hebo", color=(1, 1, 1))
        page.insert_text((30, 75), validity, fontsize=12, fontname="helv", color=(1, 1, 1))
        cell_w, cell_h = (W - 40) / cols, (H - 120) / rows
        for i, p in enumerate(products[start:start + per_page]):
            c, r = i % cols, i // cols
            x0, y0 = 20 + c * cell_w, 105 + r * cell_h
            box = pymupdf.Rect(x0 + 5, y0 + 5, x0 + cell_w - 5, y0 + cell_h - 5)
            page.draw_rect(box, color=(0.8, 0.8, 0.8), width=1)
            photo = pymupdf.Rect(box.x0 + 10, box.y0 + 10, box.x0 + 150, box.y0 + 115)
            page.insert_image(photo, stream=_photo(p.color))
            page.insert_text((box.x0 + 10, box.y0 + 140), p.name, fontsize=13, fontname="hebo")
            page.insert_text((box.x0 + 10, box.y0 + 158), p.size, fontsize=10, fontname="helv")
            euros, cents = price_parts(p.price_cents)
            page.insert_text((box.x0 + 160, box.y0 + 80), f"{euros},{cents}", fontsize=34, fontname="hebo",
                             color=(0.84, 0.15, 0.18))
            if p.old_price_cents:
                oe, oc = price_parts(p.old_price_cents)
                page.insert_text((box.x0 + 160, box.y0 + 40), f"{oe},{oc}", fontsize=12, fontname="helv",
                                 color=(0.3, 0.3, 0.3))
                pct = round((p.old_price_cents - p.price_cents) * 100 / p.old_price_cents)
                page.insert_text((box.x0 + 160, box.y0 + 105), f"-{pct}%", fontsize=14, fontname="hebo")
        page.insert_text((W - 80, H - 15), f"Pagina {doc.page_count}", fontsize=8, fontname="helv")
    data = doc.tobytes()
    doc.close()
    return data
