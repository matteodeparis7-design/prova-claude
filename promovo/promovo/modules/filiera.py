"""Filiera vicina: i produttori del territorio, con la distanza vera dal negozio.

L'unica cosa che il supermercato di quartiere ha e la grande catena no è il legame con il territorio. Il negozio
inserisce una volta i suoi produttori (nome, comune, cosa fanno, una foto, una frase vera); Promovo:
- calcola la distanza dal negozio (in linea d'aria, dal centro del comune del produttore, con OpenStreetMap);
- riconosce nel volantino i prodotti che vengono da loro;
- prepara il post «Conosci chi lo produce?» (un produttore diverso ogni settimana), la mappa della filiera da
  pubblicare e le etichette da scaffale «a 12 km da qui».

Promovo usa solo quello che scrive il negozio: non inventa storie, qualità o metodi di produzione.
Non usa «km 0» (in alcune regioni ha un significato di legge preciso): scrive la distanza calcolata.
Nome, foto e frase del produttore vanno nei contenuti pubblici solo con il suo consenso (diritto al nome e
all'immagine, artt. 7 e 10 c.c., art. 96 L. 633/1941): il negozio lo conferma quando inserisce il produttore.
"""
from __future__ import annotations

import math
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Offer, Producer, Store
from ..money import format_eur
from . import geo as geomod
from .products import tokens
from .video.render import (INK, WHITE, fit_text, font, hex_rgb, logo_image, mix, pill, product_visual,
                           readable_on_paper, soft_background, text_layer)

EARTH = (122, 84, 40)            # il colore della Filiera vicina (terra), uguale per tutti i negozi
LIMITS = {"name": 120, "town": 120, "what": 120, "story": 300, "keywords": 200}


class FilieraError(ValueError):
    pass


def clean(data: dict) -> dict:
    out = {}
    for k, n in LIMITS.items():
        v = " ".join(str(data.get(k) or "").split()).strip()
        if len(v) > n:
            raise FilieraError(f"«{k}» è troppo lungo (al massimo {n} caratteri).")
        out[k] = v
    if len(out["name"]) < 2:
        raise FilieraError("Scrivi il nome del produttore.")
    if len(out["town"]) < 2:
        raise FilieraError("Scrivi il comune del produttore: serve per calcolare la distanza.")
    if len(out["what"]) < 2:
        raise FilieraError("Scrivi cosa produce (es. «mozzarella e ricotta»).")
    if str(data.get("consent") or "").lower() not in ("1", "true", "on", "yes", "si", "sì"):
        raise FilieraError("Serve il consenso del produttore a usare nome, foto e frase nei contenuti del negozio.")
    from .compliance import text_issues
    problems = text_issues(f"{out['what']} {out['story']}")
    if problems:
        raise FilieraError("Da correggere: " + "; ".join(problems) + ".")
    return out


def public(producers: list[Producer]) -> list[Producer]:
    """I produttori che hanno dato il consenso: solo loro finiscono nei contenuti pubblici."""
    return [p for p in producers if p.consent_at is not None]


def km_text(km: float | None) -> str:
    if km is None:
        return ""
    if km < 1:
        return "a meno di 1 km da qui"
    return f"a circa {int(round(km))} km da qui"


def locate(session: Session, store: Store, p: Producer, fetch=geomod.http_json) -> None:
    """Coordinate del comune del produttore e distanza dal negozio. In caso di problemi resta l'errore da mostrare."""
    try:
        slat, slon, _ = geomod.locate(store, fetch)
        c = geomod._cached(("comune", geomod._norm(p.town)), 30 * 86400,
                              lambda: geomod.city_center(p.town, fetch))
        if c is None:
            raise geomod.GeoUnavailable(f"non trovo il comune «{p.town}» sulla mappa: controlla come è scritto")
        p.lat, p.lon = c[0], c[1]
        p.km = round(geomod.distance_m(slat, slon, p.lat, p.lon) / 1000, 1)
        p.geo_error = ""
    except geomod.GeoUnavailable as exc:
        p.km = None
        p.geo_error = str(exc)[:200]
    session.flush()


def _words(p: Producer) -> set[str]:
    return tokens(p.keywords or p.what)


def matches(producers: list[Producer], offers: list[Offer]) -> dict[int, list[Offer]]:
    """Le offerte del volantino che vengono da ciascun produttore (parole in comune nel nome del prodotto)."""
    out: dict[int, list[Offer]] = {}
    for p in producers:
        w = _words(p)
        if not w:
            continue
        hit = [o for o in offers if w & tokens(" ".join(x for x in (o.name, o.brand) if x))]
        if hit:
            out[p.id] = hit
    return out


def of_the_week(producers: list[Producer], offers: list[Offer], today: date) -> Producer | None:
    """Il produttore da raccontare questa settimana: a turno, prima quelli con prodotti nel volantino."""
    producers = public(producers)
    if not producers:
        return None
    week = today.isocalendar()[1]
    producers = [p for p in producers if p.km is not None] or producers     # prima quelli con la distanza vera
    m = matches(producers, offers)
    pool = [p for p in producers if p.id in m] or producers
    pool = sorted(pool, key=lambda p: p.id)
    return pool[week % len(pool)]


def write_text(store: Store, p: Producer, offers: list[Offer]) -> str:
    tone = store.tone or "familiare"
    emoji = tone in ("familiare", "giovane")
    voi = tone == "elegante"
    what = p.what[0].upper() + p.what[1:]
    lines = [("🌾 " if emoji else "") + "Conosci chi lo produce?", ""]
    dist = km_text(p.km)
    lines.append(f"{what}: da {p.name}, a {p.town}" + (f", {dist}." if dist else "."))
    if p.story:
        lines.append(p.story if p.story.endswith((".", "!", "?")) else p.story + ".")
    if offers:
        o = offers[0]
        lines.append(f"Questa settimana {('lo trovate' if voi else 'lo trovi')} anche in offerta: {o.name} a "
                     f"{format_eur(o.price_cents)}.")
    else:
        lines.append("Lo " + ("trovate" if voi else "trovi") + " sui nostri scaffali.")
    where = ", ".join(x for x in (store.address, store.city) if x)
    if where:
        lines += ["", ("📍 " if emoji else "") + f"{store.name} · {where}"]
    town_tag = "#" + "".join(ch for ch in p.town.title() if ch.isalnum())
    lines += ["", f"#prodottilocali #territorio {town_tag}"]
    return "\n".join(lines)


# ----------------------------------------------------------------- grafiche

def post_image(store: Store, p: Producer) -> Image.Image:
    """Post 1080x1350 «Conosci chi lo produce?»."""
    W, H = 1080, 1350
    u = 1.0
    brand = hex_rgb(store.brand_color)
    img = soft_background(W, H, mix(EARTH, brand, 0.2), u)
    d = ImageDraw.Draw(img)
    pad = 64
    badge = pill("FILIERA VICINA", 32, EARTH)
    logo = logo_image(store.logo_path or None, 280, 90, (250, 247, 240))
    y = 60
    top_h = max(badge.height, logo.height if logo is not None else 0)
    if logo is not None:
        img.alpha_composite(logo, (pad, y + (top_h - logo.height) // 2))
    else:
        fs, ls = fit_text(store.name, 520, 60, 40, True, 1)
        d.text((pad, y + top_h // 2), ls[0], font=fs, fill=readable_on_paper(brand), anchor="lm")
    img.alpha_composite(badge, (W - pad - badge.width, y + (top_h - badge.height) // 2))
    y += top_h + 50
    fh, lh = fit_text("Conosci chi lo produce?", W - 2 * pad, 200, 92, "display", 2)
    hl = text_layer(lh, fh, INK, "center")
    img.alpha_composite(hl, ((W - hl.width) // 2, y))
    y += hl.height + 30
    vis_h = 430
    vis = product_visual(p.photo_path or None, W - 2 * pad, vis_h, EARTH, u, p.name)
    img.alpha_composite(vis, (pad, y))
    y += vis_h + 26
    fn, ln = fit_text(p.name, W - 2 * pad, 130, 64, True, 2, min_size=34)
    nl = text_layer(ln, fn, INK, "center")
    img.alpha_composite(nl, ((W - nl.width) // 2, y))
    y += nl.height + 6
    fw, lw = fit_text(p.what, W - 2 * pad, 100, 42, False, 2)
    wl = text_layer(lw, fw, (90, 94, 106), "center")
    img.alpha_composite(wl, ((W - wl.width) // 2, y))
    y += wl.height + 30
    place = p.town + (f" · {int(round(p.km))} km da qui" if p.km is not None and p.km >= 1 else
                      (" · meno di 1 km da qui" if p.km is not None else ""))
    chip = pill(place, 38, EARTH)
    if chip.width > W - 2 * pad:
        chip = chip.resize((W - 2 * pad, int(chip.height * (W - 2 * pad) / chip.width)), Image.LANCZOS)
    img.alpha_composite(chip, ((W - chip.width) // 2, y))
    where = ", ".join(x for x in (store.address, store.city) if x) or store.name
    fa, la = fit_text(f"Lo trovi da noi · {where}", W - 2 * pad, 54, 34, True, 1)
    d.text((W // 2, H - 90), la[0], font=fa, fill=readable_on_paper(brand), anchor="mm")
    d.text((W // 2, H - 44), "Distanza in linea d'aria dal comune del produttore", font=font(22),
           fill=(120, 122, 130), anchor="mm")
    return img.convert("RGB")


def _bearing_xy(slat: float, slon: float, lat: float, lon: float) -> tuple[float, float]:
    """Direzione dal negozio al produttore come vettore unitario sullo schermo (nord in alto)."""
    dx = (lon - slon) * math.cos(math.radians(slat))
    dy = lat - slat
    n = math.hypot(dx, dy) or 1.0
    return dx / n, -dy / n


def map_image(store: Store, producers: list[Producer], center: tuple[float, float]) -> Image.Image:
    """La mappa della filiera: il negozio al centro, i produttori nella loro direzione vera e alla loro distanza."""
    ps = [p for p in producers if p.km is not None and p.lat is not None]
    W, H = 1080, 1350
    brand = hex_rgb(store.brand_color)
    img = soft_background(W, H, mix(EARTH, brand, 0.2), 1.0)
    d = ImageDraw.Draw(img)
    pad = 64
    badge = pill("FILIERA VICINA", 32, EARTH)
    img.alpha_composite(badge, ((W - badge.width) // 2, 60))
    n = len(ps)
    far = max((p.km for p in ps), default=10)
    title = f"I nostri {n} produttori" if n != 1 else "Il nostro produttore"
    fh, lh = fit_text(title, W - 2 * pad, 110, 80, "display", 1)
    d.text((W // 2, 190), lh[0], font=fh, fill=INK, anchor="mm")
    sub = f"tutti entro {int(math.ceil(far))} km da qui" if n > 1 else (km_text(ps[0].km) if ps else "")
    d.text((W // 2, 265), sub, font=font(40, True), fill=EARTH, anchor="mm")
    cx, cy, R = W // 2, 760, 400
    scale_km, rings = 10.0, [5.0, 10.0]
    for step in (0.5, 1, 2, 2.5, 5, 10, 20, 25, 50, 100, 200):         # cerchi a distanze tonde, da 2 a 4
        k = math.ceil(far * 1.05 / step)
        if k <= 4:
            k = max(k, 2)
            scale_km, rings = step * k, [step * i for i in range(1, k + 1)]
            break
    for rk in rings:
        r = R * rk / scale_km
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=mix(EARTH, WHITE, 0.6), width=3)
        lab = f"{rk:g} km".replace(".", ",")
        d.text((cx, cy - r - 6), lab, font=font(22, True), fill=mix(EARTH, WHITE, 0.25), anchor="mb")
    # punti nella loro direzione vera
    dots = []
    for p in ps:
        ux, uy = _bearing_xy(center[0], center[1], p.lat, p.lon)
        r = max(R * (p.km or 0) / scale_km, 40)
        dots.append((p, cx + ux * r, cy + uy * r))
    # scritte: dal lato esterno del punto, mai sopra il negozio né una sopra l'altra (con una linea se spostate)
    fl, fk = font(28, True), font(22)
    store_box = (cx - 150, cy - 40, cx + 150, cy + 90)
    boxes = [store_box]
    placed = []
    for p, x, y in sorted(dots, key=lambda t: t[2]):
        label = p.name if len(p.name) <= 22 else p.name[:21] + "…"
        km = f"{p.town} · {int(round(p.km))} km" if p.km >= 1 else f"{p.town} · <1 km"
        wl, hl = max(fl.getlength(label), fk.getlength(km)), 62
        right = x >= cx
        if right and x + 26 + wl > W - 24:          # non c'è posto a destra: la scritta va a sinistra del punto
            right = False
        elif not right and x - 26 - wl < 24:
            right = True
        lx = x + 26 if right else x - 26 - wl
        lx = min(max(lx, 24), W - 24 - wl)
        ly = y - hl / 2

        def hits(yy):
            return any(lx < b[2] + 8 and lx + wl > b[0] - 8 and yy < b[3] + 6 and yy + hl > b[1] - 6 for b in boxes)
        step, k = 0, 0
        while hits(ly + step) and k < 40:
            k += 1
            step = (k + 1) // 2 * 18 * (1 if k % 2 else -1)
        ly += step
        boxes.append((lx, ly, lx + wl, ly + hl))
        placed.append((p, x, y, lx, ly, wl, right, label, km))
    for p, x, y, lx, ly, wl, right, label, km in placed:
        if abs(ly + 31 - y) > 14:                                 # scritta spostata: linea fino al suo punto
            ax = lx if right else lx + wl
            d.line((x, y, ax, ly + 31), fill=mix(EARTH, WHITE, 0.4), width=2)
        d.text((lx, ly), label, font=fl, fill=INK)
        d.text((lx, ly + 34), km, font=fk, fill=(90, 94, 106))
    for p, x, y in dots:
        d.ellipse((x - 14, y - 14, x + 14, y + 14), fill=EARTH, outline=WHITE, width=4)
    d.ellipse((cx - 30, cy - 30, cx + 30, cy + 30), fill=brand, outline=WHITE, width=6)
    fs, ls = fit_text(store.name, 300, 50, 30, True, 1)
    tw = fs.getlength(ls[0])
    d.rounded_rectangle((cx - tw / 2 - 14, cy + 38, cx + tw / 2 + 14, cy + 80), radius=20, fill=WHITE)
    d.text((cx, cy + 59), ls[0], font=fs, fill=readable_on_paper(brand), anchor="mm")
    d.text((W // 2, H - 84), "Comprare vicino: conosciamo chi c'è dietro a quello che vendiamo.", font=font(30, True),
           fill=INK, anchor="mm")
    d.text((W // 2, H - 40), "Distanze in linea d'aria · Dati della mappa © OpenStreetMap contributors",
           font=font(20), fill=(120, 122, 130), anchor="mm")
    return img.convert("RGB")


# ----------------------------------------------------------------- etichette da scaffale

def label_image(store: Store, p: Producer) -> Image.Image:
    w, h = 1240, 877                     # 105 x 74 mm a 300 dpi: 8 per foglio A4
    img = Image.new("RGB", (w, h), WHITE)
    d = ImageDraw.Draw(img)
    band = 150
    d.rectangle((0, 0, w, band), fill=EARTH)
    d.text((50, band // 2), "FILIERA VICINA", font=font(64, "display"), fill=WHITE, anchor="lm")
    if p.km is not None:
        big = f"{int(round(p.km))} km" if p.km >= 1 else "<1 km"
        d.text((w - 50, band // 2), big, font=font(72, "display"), fill=WHITE, anchor="rm")
    foot = 130
    fn, ln = fit_text(p.name, w - 100, 230, 96, True, 2, min_size=48)
    nl = text_layer(ln, fn, INK)
    fw, lw = fit_text(p.what, w - 100, 140, 60, False, 2)
    wl = text_layer(lw, fw, (90, 94, 106))
    block = nl.height + 14 + wl.height
    y = band + (h - foot - band - block) // 2
    img.paste(nl, (50, y), nl)
    img.paste(wl, (50, y + nl.height + 14), wl)
    d.rectangle((0, h - foot, w, h), fill=mix(EARTH, WHITE, 0.88))
    place = f"Da {p.town}" + (f", {km_text(p.km)}" if p.km is not None else "")
    fp, lp = fit_text(place, w - 100, 80, 44, True, 1)
    d.text((50, h - foot // 2), lp[0], font=fp, fill=EARTH, anchor="lm")
    return img


def labels_pdf(store: Store, producers: list[Producer], out: Path) -> Path:
    if not producers:
        raise FilieraError("Nessun produttore da stampare.")
    W, H = 2480, 3508
    tw, th = W // 2, H // 4
    pages = []
    for start in range(0, len(producers), 8):
        page = Image.new("RGB", (W, H), WHITE)
        for k, p in enumerate(producers[start:start + 8]):
            lab = label_image(store, p)
            lab.thumbnail((tw - 36, th - 36), Image.LANCZOS)
            page.paste(lab, ((k % 2) * tw + (tw - lab.width) // 2, (k // 2) * th + (th - lab.height) // 2))
        dd = ImageDraw.Draw(page)
        for x in range(0, W, 28):
            for r in range(1, 4):
                dd.line((x, r * th, x + 14, r * th), fill=(170, 170, 170), width=2)
        for y in range(0, H, 28):
            dd.line((tw, y, tw, y + 14), fill=(170, 170, 170), width=2)
        pages.append(page)
    out.parent.mkdir(parents=True, exist_ok=True)
    pages[0].save(out, "PDF", resolution=300, save_all=True, append_images=pages[1:])
    return out


def store_producers(session: Session, store: Store) -> list[Producer]:
    return list(session.scalars(select(Producer).where(Producer.store_id == store.id).order_by(Producer.km.is_(None),
                                                                                                Producer.km, Producer.id)))
