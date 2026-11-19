"""Il calendario dei portafogli e la spesa a budget.

Le persone non fanno la spesa allo stesso modo tutto il mese: a inizio mese (pensioni e molti stipendi) si fa scorta,
a fine mese si contano gli euro, a dicembre arriva la tredicesima. Promovo sa in che momento del mese siamo e:
- consiglia cosa spingere e quando pubblicare;
- compone «la spesa a budget»: un cestino vero con le offerte del volantino, con il totale calcolato al centesimo
  e il risparmio rispetto ai prezzi senza offerta. Solo numeri veri: niente porzioni o «cene per 4» inventate.
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta

from PIL import Image, ImageDraw

from ..models import Flyer, Offer, Store
from ..money import format_eur
from .video.service import offer_image
from .video.render import (INK, WHITE, fit_text, font, hex_rgb, logo_image, pill, price_block, product_visual,
                           readable_on_paper, scaled, soft_background, text_layer)

AMOUNTS = (10, 15, 20, 25, 30, 40, 50)
# la spesa di tutti i giorni prima, il resto dopo; fuori dal cestino: casa, persona, animali, alcolici
PRIORITY = ["pasta e riso", "latte e latticini", "uova", "frutta e verdura", "pane e forno", "carne", "pesce",
            "salumi e formaggi", "dispensa", "colazione", "surgelati", "bevande", "dolci e snack", "infanzia"]
EXCLUDED = {"igiene casa", "cura persona", "animali", "vino e alcolici"}
MAX_ITEMS = 9


# ----------------------------------------------------------------- il momento del mese

def moment(day: date) -> dict:
    last = calendar.monthrange(day.year, day.month)[1]
    if day.month == 12 and day.day <= 24:
        return {"key": "tredicesima", "title": "Dicembre: tredicesima e feste",
                "advice": "Per molti arriva la tredicesima e si prepara il Natale: spingi i prodotti delle feste e "
                          "le confezioni da condividere."}
    if day.day <= 7:
        return {"key": "scorta", "title": "Inizio mese: si fa scorta",
                "advice": "Per molte famiglie sono arrivati pensioni e stipendi: funzionano le confezioni grandi, "
                          "le scorte per la dispensa e le offerte «più compri, più risparmi»."}
    if day.day <= 19:
        return {"key": "regolare", "title": "Metà mese: la spesa di tutti i giorni",
                "advice": "Spesa regolare: puntano bene il fresco, l'idea della settimana e i prodotti sotto l'euro."}
    if day.day <= 26:
        return {"key": "budget", "title": "Fine mese: si contano gli euro",
                "advice": "I portafogli sono più leggeri: è il momento della spesa a budget. Pubblicala in "
                          "questi giorni, meglio il giovedì o il venerdì."}
    return {"key": "stipendi", "title": "Fine mese: arrivano gli stipendi",
            "advice": f"Intorno al 27 arrivano molti stipendi (e dall'1 le pensioni): buon momento per la spesa "
                      f"del fine settimana e le scorte, fino al {last}."}


def best_day(flyer: Flyer | None, today: date) -> tuple[date, str]:
    """Il giorno migliore per pubblicare la spesa a budget, dentro le date del volantino."""
    start = max(today, flyer.valid_from) if flyer is not None and flyer.valid_from else today
    end = flyer.valid_to if flyer is not None and flyer.valid_to and flyer.valid_to >= start else start + timedelta(days=6)
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    tight = [d for d in days if 20 <= d.day <= 26]
    if tight:
        pick = next((d for d in tight if d.weekday() in (3, 4)), tight[0])
        return pick, "a fine mese, quando si contano gli euro"
    pick = next((d for d in days if d.weekday() in (3, 4)), days[0])
    return pick, "verso il fine settimana, quando si prepara la spesa grande"


# ----------------------------------------------------------------- il cestino

@dataclass
class Basket:
    amount_cents: int
    items: list[Offer] = field(default_factory=list)

    @property
    def total(self) -> int:
        return sum(o.price_cents for o in self.items)

    @property
    def saving(self) -> int:
        return sum((o.old_price_cents - o.price_cents) for o in self.items
                   if o.old_price_cents and o.old_price_cents > o.price_cents)


def _ok(o: Offer) -> bool:
    return o.price_cents > 0 and (o.category or "altro") not in EXCLUDED


def make_basket(offers: list[Offer], amount_cents: int) -> Basket | None:
    """Il cestino più vario che sta nel budget: prima la spesa di tutti i giorni (il più economico di ogni reparto),
    poi le altre offerte finché c'è posto. Almeno 3 prodotti, altrimenti niente."""
    pool = [o for o in offers if _ok(o)]
    b = Basket(amount_cents)
    if not pool:
        return None
    by_cat: dict[str, list[Offer]] = {}
    for o in pool:
        by_cat.setdefault(o.category or "altro", []).append(o)
    order = PRIORITY + sorted(c for c in by_cat if c not in PRIORITY)
    for cat in order:                                  # un prodotto per reparto, il più conveniente
        for o in sorted(by_cat.get(cat, []), key=lambda x: (not x.price_verified, x.price_cents)):
            if b.total + o.price_cents <= amount_cents and len(b.items) < MAX_ITEMS:
                b.items.append(o)
                break
    for o in sorted(pool, key=lambda x: (-(x.discount_percent or 0), x.price_cents)):   # poi i più scontati
        if o not in b.items and b.total + o.price_cents <= amount_cents and len(b.items) < MAX_ITEMS:
            b.items.append(o)
    if len(b.items) < 3:
        return None
    b.items.sort(key=lambda o: order.index(o.category) if o.category in order else 99)
    return b


def amounts_for(offers: list[Offer]) -> list[int]:
    """I budget che hanno senso con queste offerte (almeno 3 prodotti)."""
    return [a for a in AMOUNTS if make_basket(offers, a * 100) is not None]


def _label(o: Offer) -> str:
    name = " ".join(x for x in (o.brand, o.name) if x)
    desc = o.description or ""
    if not desc and "kg" in (o.unit_price_text or "").lower():
        desc = "1 kg"
    return f"{name} {desc}".strip()


def until(flyer: Flyer) -> str:
    return f"fino al {flyer.valid_to.day}/{flyer.valid_to.month}" if flyer.valid_to else "fino a esaurimento"


def write_text(store: Store, flyer: Flyer, b: Basket) -> str:
    tone = store.tone or "familiare"
    emoji = tone in ("familiare", "giovane")
    voi = tone == "elegante"
    eur = b.amount_cents // 100
    lines = [("🛒 " if emoji else "") + f"La spesa a {eur} € di questa settimana", ""]
    lines.append(f"Con le offerte del volantino {'portate' if voi else 'porti'} a casa {len(b.items)} prodotti per "
                 f"{format_eur(b.total)}:")
    for o in b.items:
        lines.append(f"• {_label(o)} – {format_eur(o.price_cents)}")
    if b.saving > 0:
        lines.append(f"{'Risparmiate' if voi else 'Risparmi'} {format_eur(b.saving)} rispetto ai prezzi senza offerta.")
    lines.append(f"Offerte valide {until(flyer)}, salvo esaurimento.")
    where = ", ".join(x for x in (store.address, store.city) if x)
    if where:
        lines += ["", ("📍 " if emoji else "") + f"{store.name} · {where}"]
    lines += ["", "#spesaabudget #risparmio #offerte"]
    return "\n".join(lines)


def image(store: Store, flyer: Flyer, b: Basket) -> Image.Image:
    W, H = 1080, 1350
    brand, accent = hex_rgb(store.brand_color), hex_rgb(store.accent_color)
    img = soft_background(W, H, brand, 1.0)
    d = ImageDraw.Draw(img)
    pad = 60
    y = 52
    logo = logo_image(store.logo_path or None, 260, 84, (250, 247, 240))
    if logo is not None:
        img.alpha_composite(logo, (pad, y))
    else:
        fs, ls = fit_text(store.name, 520, 60, 40, True, 1)
        d.text((pad, y + 30), ls[0], font=fs, fill=readable_on_paper(brand), anchor="lm")
    vb = pill(until(flyer).capitalize(), 28, INK)
    img.alpha_composite(vb, (W - pad - vb.width, y + 14))
    y += 120
    ft, lt = fit_text(f"La spesa a {b.amount_cents // 100} €", W - 2 * pad, 130, 104, "display", 1)
    d.text((W // 2, y + 50), lt[0], font=ft, fill=INK, anchor="mm")
    y += 130
    d.text((W // 2, y), f"{len(b.items)} prodotti in offerta, il totale è giusto al centesimo", font=font(32, True),
           fill=(90, 94, 106), anchor="mm")
    y += 46
    # elenco: foto piccola, nome, prezzo
    foot = 300
    row_h = min(104, (H - foot - y) // max(1, len(b.items)))
    card = Image.new("RGBA", (W - 2 * pad, row_h * len(b.items) + 24), (0, 0, 0, 0))
    ImageDraw.Draw(card).rounded_rectangle((0, 0, card.width - 1, card.height - 1), radius=28, fill=WHITE + (255,))
    cd = ImageDraw.Draw(card)
    for i, o in enumerate(b.items):
        ry = 12 + i * row_h
        th = product_visual(offer_image(o, cut=False), row_h - 14, row_h - 14, brand, 0.35, "")
        card.alpha_composite(th, (18, ry + 7))
        fn, ln = fit_text(_label(o), card.width - row_h - 260, row_h - 20, 34, True, 2, min_size=22)
        nl = text_layer(ln, fn, INK)
        card.alpha_composite(nl, (row_h + 16, ry + (row_h - nl.height) // 2))
        cd.text((card.width - 28, ry + row_h // 2), format_eur(o.price_cents), font=font(38, "display"),
                fill=readable_on_paper(brand), anchor="rm")
        if i:
            cd.line((row_h + 16, ry, card.width - 24, ry), fill=(236, 232, 224), width=2)
    img.alpha_composite(card, (pad, y))
    # totale e risparmio
    yb = H - foot + 30
    d.text((pad, yb + 40), "Totale", font=font(46, True), fill=INK, anchor="lm")
    price = price_block(b.total, 130, brand)
    img.alpha_composite(price, (pad, yb + 74))
    if b.saving > 0:
        sv = pill(f"Risparmi {format_eur(b.saving)}", 40, accent)
        if sv.width > W - 2 * pad - price.width - 30:
            sv = scaled(sv, (W - 2 * pad - price.width - 30) / sv.width)
        img.alpha_composite(sv, (W - pad - sv.width, yb + 74 + (130 - sv.height) // 2))
    where = ", ".join(x for x in (store.address, store.city) if x) or store.name
    fw, lw = fit_text(where, W - 2 * pad, 46, 30, True, 1)
    d.text((W // 2, H - 52), lw[0], font=fw, fill=readable_on_paper(brand), anchor="mm")
    return img.convert("RGB")
