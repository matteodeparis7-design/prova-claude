"""Generatore di un volantino PDF di prova (per test e dimostrazioni).

Crea pagine con riquadri prodotto: foto (immagine), nome, formato, prezzo,
prezzo barrato e sconto, come in un volantino vero.
"""
from __future__ import annotations

import io
from dataclasses import dataclass

from . import pdfdoc
from PIL import Image, ImageDraw

from .money import price_parts

# Caratteri incorporati nel PDF, come nei volantini veri (Liberation Sans, licenza SIL OFL 1.1).
_FONTS_DIR = __import__("pathlib").Path(__file__).resolve().parent / "assets" / "fonts"
BOLD, REGULAR = str(_FONTS_DIR / "LiberationSans-Bold.ttf"), str(_FONTS_DIR / "LiberationSans-Regular.ttf")


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


@dataclass
class FlyerStyle:
    """Varianti grafiche, per mettere alla prova il lettore come con volantini veri diversi."""
    cols: int = 2
    rows: int = 3
    page_size: tuple[float, float] = (595, 842)                 # A4 verticale, in punti
    price_style: str = "red"                                    # red | black | badge (bianco su riquadro)
    euro_sign: bool = False                                     # "€ 1,99" invece di "1,99"
    unit_price: bool = False                                    # "al kg € 7,90" in piccolo
    background: tuple[float, float, float] = (1, 1, 1)
    header: tuple[float, float, float] = (0.84, 0.15, 0.18)


def build_sample_flyer(products: list[SampleProduct] | None = None, per_page: int | None = None,
                       validity: str = "Offerte valide dal 13 al 22 novembre 2026",
                       banner: str = "SUPERSTORE", style: FlyerStyle | None = None,
                       illustrated: bool = False) -> bytes:
    products = products if products is not None else DEFAULT_PRODUCTS
    st = style or FlyerStyle()
    per_page = per_page or st.cols * st.rows
    doc = pdfdoc.new_document()
    W, H = st.page_size
    cols, rows = st.cols, st.rows
    red = (0.84, 0.15, 0.18)
    for start in range(0, max(len(products), 1), per_page):
        page = doc.new_page(width=W, height=H)
        page.insert_font(fontname="hebo", fontfile=BOLD)
        page.insert_font(fontname="helv", fontfile=REGULAR)
        if st.background != (1, 1, 1):
            page.draw_rect(page.rect, color=None, fill=st.background)
        page.draw_rect(pdfdoc.Rect(0, 0, W, 90), color=None, fill=st.header)
        page.insert_text((30, 50), banner, fontsize=30, fontname="hebo", color=(1, 1, 1))
        page.insert_text((30, 75), validity, fontsize=12, fontname="helv", color=(1, 1, 1))
        cell_w, cell_h = (W - 40) / cols, (H - 120) / rows
        k = min(cell_w / 277, cell_h / 240)          # scala degli elementi rispetto alla cella standard
        for i, p in enumerate(products[start:start + per_page]):
            c, r = i % cols, i // cols
            x0, y0 = 20 + c * cell_w, 105 + r * cell_h
            box = pdfdoc.Rect(x0 + 5, y0 + 5, x0 + cell_w - 5, y0 + cell_h - 5)
            page.draw_rect(box, color=(0.8, 0.8, 0.8), fill=(1, 1, 1), width=1)
            photo = pdfdoc.Rect(box.x0 + 10 * k, box.y0 + 10 * k, box.x0 + 150 * k, box.y0 + 115 * k)
            art = None
            if illustrated:
                from .demo_art import product_png
                art = product_png(p.name)
            page.insert_image(photo, stream=art or _photo(p.color))
            page.insert_text((box.x0 + 10 * k, box.y0 + 140 * k), p.name, fontsize=13 * k, fontname="hebo")
            page.insert_text((box.x0 + 10 * k, box.y0 + 158 * k), p.size, fontsize=10 * k, fontname="helv")
            euros, cents = price_parts(p.price_cents)
            label = f"{'€ ' if st.euro_sign else ''}{euros},{cents}"
            px, py, fs = box.x0 + 160 * k, box.y0 + 80 * k, 34 * k
            if st.price_style == "badge":
                tw = pdfdoc.Font(fontfile=BOLD).text_length(label, fontsize=fs)
                page.draw_rect(pdfdoc.Rect(px - 4 * k, py - fs * 0.85, px + tw + 4 * k, py + fs * 0.25),
                               color=None, fill=red)
                page.insert_text((px, py), label, fontsize=fs, fontname="hebo", color=(1, 1, 1))
            else:
                page.insert_text((px, py), label, fontsize=fs, fontname="hebo",
                                 color=red if st.price_style == "red" else (0.1, 0.1, 0.1))
            if p.old_price_cents:
                oe, oc = price_parts(p.old_price_cents)
                page.insert_text((px, box.y0 + 40 * k), f"{oe},{oc}", fontsize=12 * k, fontname="helv",
                                 color=(0.3, 0.3, 0.3))
                pct = round((p.old_price_cents - p.price_cents) * 100 / p.old_price_cents)
                page.insert_text((px, box.y0 + 105 * k), f"-{pct}%", fontsize=14 * k, fontname="hebo")
            if st.unit_price:
                ue, uc = price_parts(p.price_cents * 2)
                page.insert_text((box.x0 + 10 * k, box.y0 + 172 * k), f"al kg {ue},{uc}", fontsize=7 * k,
                                 fontname="helv")
        page.insert_text((W - 80, H - 15), f"Pagina {doc.page_count}", fontsize=8, fontname="helv")
    data = doc.tobytes()
    doc.close()
    return data


def make_image_only(pdf: bytes, dpi: int = 150) -> bytes:
    """Converte ogni pagina in un'immagine senza testo, come molti volantini veri."""
    src = pdfdoc.open(stream=pdf, filetype="pdf")
    out = pdfdoc.new_document()
    for page in src:
        pix = page.get_pixmap(dpi=dpi, alpha=False)
        new = out.new_page(width=page.rect.width, height=page.rect.height)
        new.insert_image(new.rect, stream=pix.tobytes("png"))
    data = out.tobytes()
    out.close()
    src.close()
    return data
