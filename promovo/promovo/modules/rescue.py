"""Salvaspreco: la merce vicina alla scadenza diventa un'offerta lampo, e lo spreco evitato diventa un vanto.

Il flusso, pensato per 30 secondi la mattina e 5 la sera:
1. si sceglie il prodotto (dal volantino, oppure scritto a mano con una foto), quanti pezzi, il prezzo e la data;
2. Promovo controlla che si possa vendere, consiglia lo sconto in base al tempo che resta, e prepara la storia
   (Instagram, Facebook, stato WhatsApp), il post, i testi e il cartellino «Salvami» da stampare;
3. la sera si segna quanti pezzi sono stati venduti: Promovo tiene il conto dei chili di cibo salvato e degli euro
   recuperati, e a fine mese prepara il post «Questo mese abbiamo salvato … dallo spreco».

Regole (Reg. UE 1169/2011, art. 24; L. 166/2016 «legge Gadda»):
- un prodotto con data di scadenza («da consumarsi entro») superata NON si può vendere: Promovo lo blocca;
- dopo il termine minimo di conservazione («da consumarsi preferibilmente entro») si può vendere se integro e ben
  conservato: Promovo lo permette e scrive la data nei testi, per trasparenza;
- Promovo non inventa niente sul prodotto: usa solo nome, formato, prezzi, date e motivo indicati dal negozio.
"""
from __future__ import annotations

import calendar
import shutil
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Offer, Rescue, Store
from ..money import format_eur
from .radar.service import quantity
from .video.render import (INK, WHITE, brand_background, discount_burst, fit_text, font, hex_rgb, logo_image, mix,
                           old_price_line, pill, price_block, product_visual, readable_on_paper, scaled,
                           soft_background, text_layer, text_on)

GREEN = (28, 128, 70)            # il colore del Salvaspreco, uguale per tutti i negozi: si riconosce subito
DAYS = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
MONTHS = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre",
          "ottobre", "novembre", "dicembre"]

REASONS = {
    "scadenza": "Scade a breve",
    "maturo": "Frutta e verdura molto matura",
    "forno": "Pane e forno di oggi",
    "confezione": "Confezione rovinata, prodotto integro",
    "ultimi": "Ultimi pezzi",
}
DATE_KINDS = {"scadenza": "Da consumarsi entro", "tmc": "Da consumarsi preferibilmente entro", "": ""}
UNITS = ("pezzi", "kg")

HEADLINES = {        # titoli neutri: niente giudizi sul prodotto, nessun accordo di genere da sbagliare
    "scadenza": ["Salvami dallo spreco!", "Da salvare oggi", "Un affare che non spreca"],
    "maturo": ["Da usare subito", "Salvami dallo spreco!", "Per spremute, torte e minestre"],
    "forno": ["Fine giornata, prezzo speciale", "Salvami dallo spreco!", "Il forno di oggi a prezzo di sera"],
    "confezione": ["Confezione rovinata, prodotto integro", "Salvami dallo spreco!", "Conta quello che c'è dentro"],
    "ultimi": ["Ultimi pezzi", "Gli ultimi, a prezzo speciale", "Salvami dallo spreco!"],
}
REASON_LINES = {
    "maturo": "Molto matura: ideale per spremute, frullati, marmellate, torte e minestre.",
    "forno": "Pane e prodotti da forno di oggi, a prezzo di fine giornata.",
    "confezione": "La confezione è rovinata, il prodotto dentro è integro.",
    "ultimi": "Gli ultimi pezzi rimasti, a un prezzo speciale.",
}


class RescueError(ValueError):
    pass


# ----------------------------------------------------------------- regole, sconti, pesi

def days_left(expires_on: date | None, today: date) -> int | None:
    return None if expires_on is None else (expires_on - today).days


def check_sellable(date_kind: str, expires_on: date | None, today: date) -> list[str]:
    """Blocca ciò che non si può vendere; per il resto restituisce le note da mostrare al negozio."""
    if date_kind not in DATE_KINDS:
        raise RescueError("Tipo di data non valido.")
    if date_kind and expires_on is None:
        raise RescueError("Scrivi la data stampata sulla confezione.")
    d = days_left(expires_on, today)
    notes = []
    if date_kind == "scadenza" and d is not None and d < 0:
        raise RescueError("La data di scadenza («da consumarsi entro») è passata: per legge il prodotto va tolto "
                          "dalla vendita. Non si può mettere in Salvaspreco.")
    if date_kind == "tmc" and d is not None and d < 0:
        notes.append("Il termine minimo («preferibilmente entro») è passato: si può vendere se la confezione è "
                     "integra e il prodotto ben conservato. Nei testi scriviamo la data, per trasparenza.")
    if date_kind == "scadenza" and d == 0:
        notes.append("Scade oggi: si può vendere fino a stasera. Domani va tolto dagli scaffali.")
    return notes


def suggest_discount(reason: str, date_kind: str, expires_on: date | None, today: date) -> int:
    """Lo sconto consigliato: più è vicina la data, più è forte (meglio venderlo che buttarlo)."""
    d = days_left(expires_on, today)
    if date_kind and d is not None:
        if d <= 0:
            return 50
        return {1: 40, 2: 30}.get(d, 25 if d <= 5 else 20)
    return {"forno": 50, "maturo": 40, "confezione": 30, "ultimi": 30}.get(reason, 30)


def rescue_price(price_cents: int, pct: int) -> int:
    """Prezzo scontato arrotondato a un prezzo «da cartellino» (…9 centesimi), mai sopra lo sconto scelto."""
    if price_cents <= 1:
        return price_cents
    target = price_cents * (100 - pct) / 100
    nice = (int(target) + 1) // 10 * 10 - 1
    cents = nice if nice > 0 and nice >= target * 0.9 else max(1, int(round(target)))
    return min(cents, price_cents - 1)


def unit_weight_g(name: str, description: str) -> int | None:
    """Peso (o volume, ~ grammi) di un pezzo dal formato scritto: «500 g», «4 x 125 g», «1 litro»."""
    q = quantity(description or "") or quantity(name or "")
    if q is None or q.kind not in ("massa", "volume") or q.amount <= 0:
        return None
    return int(round(q.amount))


def discount_pct(r: Rescue) -> int:
    if r.price_cents <= 0 or r.rescue_price_cents >= r.price_cents:
        return 0
    return int(round((r.price_cents - r.rescue_price_cents) * 100 / r.price_cents))


def saved_kg(r: Rescue) -> float | None:
    """Chili di cibo salvato con le vendite segnate (None se il peso non è noto)."""
    sold = r.sold_qty or 0
    if r.unit == "kg":
        return float(sold)
    if r.unit_weight_g:
        return sold * r.unit_weight_g / 1000
    return None


def qty_text(qty: float, unit: str) -> str:
    if unit == "kg":
        n = f"{qty:.1f}".rstrip("0").rstrip(".").replace(".", ",")
        return f"{n} kg"
    n = int(qty) if float(qty).is_integer() else qty
    return f"{n} {'pezzo' if n == 1 else 'pezzi'}"


def _dm(d: date) -> str:
    return f"{d.day}/{d.month}"


def until_text(r: Rescue, today: date) -> str:
    end = r.until or r.day
    if end <= today:
        return "Solo oggi"
    if (end - today).days == 1:
        return "Fino a domani"
    return f"Fino a {DAYS[end.weekday()]} {_dm(end)}"


def date_line(r: Rescue) -> str:
    if r.date_kind and r.expires_on:
        return f"{DATE_KINDS[r.date_kind]} il {_dm(r.expires_on)}"
    return ""


def product_label(r: Rescue) -> str:
    return " ".join(x for x in (r.name, r.description) if x).strip()


# ----------------------------------------------------------------- testi

def _pick(options: list[str], seed: int) -> str:
    return options[seed % len(options)]


def write_texts(store: Store, r: Rescue, today: date) -> tuple[str, str]:
    """Post per Instagram/Facebook e testo breve per lo stato WhatsApp, nel tono del negozio."""
    tone = store.tone or "familiare"
    emoji = tone in ("familiare", "giovane")
    seed = (r.id or 0) + today.toordinal()
    price, old, pct = format_eur(r.rescue_price_cents), format_eur(r.price_cents), discount_pct(r)
    what = product_label(r)
    unit_note = " al kg" if r.unit == "kg" and "kg" not in (r.description or "").lower() else ""
    head = _pick(HEADLINES.get(r.reason, HEADLINES["scadenza"]), seed)
    lines = [(("🌱 " if emoji else "") + f"Salvaspreco · {head}").strip(), ""]
    lines.append(f"{what}: {price}{unit_note} invece di {old}" + (f" (-{pct}%)." if pct else "."))
    if r.reason in REASON_LINES:
        lines.append(REASON_LINES[r.reason])
    dl = date_line(r)
    if dl:
        lines.append(dl + ".")
    left = qty_text(r.qty, r.unit)
    if tone == "essenziale":
        lines.append(f"Disponibili: {left}. {until_text(r, today)}, fino a esaurimento.")
    else:
        lines.append(f"Ne restano {left}: quando finiscono, finiscono. {until_text(r, today)}.")
        lines.append(_pick(["Sceglierlo vuol dire evitare che finisca nella spazzatura.",
                            "Un buon prezzo per te, uno spreco in meno per tutti.",
                            "Meno spreco, più risparmio: lo salviamo insieme?"], seed))
    where = ", ".join(x for x in (store.address, store.city) if x)
    if where:
        lines += ["", ("📍 " if emoji else "") + f"{store.name} · {where}"]
    tags = ["#salvaspreco", "#antispreco", "#nonsprecare"]
    for t in store.hashtags or []:
        t = t if t.startswith("#") else "#" + t
        if t.lower() not in tags and len(tags) < 8:
            tags.append(t)
    lines += ["", " ".join(tags)]
    post = "\n".join(lines).strip()
    short = (("♻️ " if emoji else "") + f"SALVASPRECO: {what} a {price}{unit_note} invece di {old}"
             + (f" (-{pct}%)" if pct else "") + f". Ne restano {left}. {until_text(r, today)}."
             + (f" {dl}." if dl else "") + f" {store.name}" + (f", {where}" if where else ""))
    return post, short


# ----------------------------------------------------------------- grafiche

def _compose(store: Store, r: Rescue, W: int, H: int, today: date) -> Image.Image:
    u = W / 1080
    brand, accent = hex_rgb(store.brand_color), hex_rgb(store.accent_color)
    tall = H / W > 1.5
    img = soft_background(W, H, mix(GREEN, brand, 0.25), u)
    d = ImageDraw.Draw(img)
    pad = int(64 * u)
    y = int((90 if tall else 56) * u)
    # testata: logo (o nome del negozio) e il bollino verde Salvaspreco
    badge = pill("SALVASPRECO", int(34 * u), GREEN)
    logo = logo_image(store.logo_path or None, int(300 * u), int(96 * u), (250, 247, 240))
    top_h = max(badge.height, logo.height if logo is not None else 0)
    if logo is not None:
        img.alpha_composite(logo, (pad, y + (top_h - logo.height) // 2))
    else:
        fs, ls = fit_text(store.name, int(W * 0.5), int(60 * u), int(40 * u), True, 1)
        d.text((pad, y + top_h // 2), ls[0], font=fs, fill=readable_on_paper(brand), anchor="lm")
    img.alpha_composite(badge, (W - pad - badge.width, y + (top_h - badge.height) // 2))
    top = y + top_h + int(30 * u)
    # piede: dove
    foot_h = int((170 if tall else 120) * u)
    where = ", ".join(x for x in (store.address, store.city) if x) or store.name
    fw, lw = fit_text(where, W - 2 * pad, int(54 * u), int(36 * u), True, 1)
    d.text((W // 2, H - int((120 if tall else 82) * u)), lw[0], font=fw, fill=readable_on_paper(brand), anchor="mm")
    fo = font(int(24 * u))
    d.text((W // 2, H - int((70 if tall else 40) * u)), "Fino a esaurimento · Meno spreco, più risparmio", font=fo,
           fill=(110, 112, 120), anchor="mm")
    room = H - foot_h - top
    block = _middle(r, W, room, u, brand, accent, tall, today)
    if block.height > room:
        block = scaled(block, room / block.height)
    img.alpha_composite(block, ((W - block.width) // 2, top + (room - block.height) // 2))
    return img.convert("RGB")


def _middle(r: Rescue, W: int, room: int, u: float, brand, accent, tall: bool, today: date) -> Image.Image:
    """Titolo, prodotto, nome, prezzo e informazioni, uno sotto l'altro (poi centrati nello spazio libero)."""
    pad = int(64 * u)
    layers: list[tuple[Image.Image, int]] = []          # (strato, spazio dopo)
    head = _pick(HEADLINES.get(r.reason, HEADLINES["scadenza"]), (r.id or 0) + today.toordinal())
    fh, lh = fit_text(head, W - 2 * pad, int((230 if tall else 170) * u), int((104 if tall else 88) * u), "display", 2)
    layers.append((text_layer(lh, fh, INK, "center"), int((40 if tall else 26) * u)))
    # prodotto con il bollino dello sconto
    vis_h = int(room * (0.36 if tall else 0.34))
    vis = product_visual(r.photo_path or None, W - 2 * pad, vis_h, GREEN, u, r.name)
    pct = discount_pct(r)
    if pct:
        burst = discount_burst(pct, int(230 * u), accent)
        vis.alpha_composite(burst, (vis.width - burst.width, 0))
    layers.append((vis, int(24 * u)))
    fn, ln = fit_text(r.name, W - 2 * pad, int(130 * u), int(62 * u), True, 2, min_size=int(34 * u))
    layers.append((text_layer(ln, fn, INK, "center"), int(4 * u)))
    if r.description:
        fd, ld = fit_text(r.description, W - 2 * pad, int(54 * u), int(40 * u), False, 1)
        layers.append((text_layer(ld, fd, (96, 100, 112), "center"), 0))
    layers[-1] = (layers[-1][0], int((36 if tall else 24) * u))
    # prezzo, prezzo di prima e «al kg»
    price = price_block(r.rescue_price_cents, int((210 if tall else 180) * u), brand)
    old = old_price_line(r.price_cents, int(40 * u), (96, 100, 112))
    gap = int(26 * u)
    row = Image.new("RGBA", (price.width + gap + old.width, price.height), (0, 0, 0, 0))
    row.alpha_composite(price, (0, 0))
    row.alpha_composite(old, (price.width + gap, price.height - old.height - int(10 * u)))
    if r.unit == "kg" and "kg" not in (r.description or "").lower():
        ImageDraw.Draw(row).text((price.width + gap, int(14 * u)), "al kg", font=font(int(30 * u), True), fill=INK)
    if row.width > W - 2 * pad:
        row = scaled(row, (W - 2 * pad) / row.width)
    layers.append((row, int((40 if tall else 28) * u)))
    # fino a quando, quanti ne restano, la data stampata
    chips = [pill(until_text(r, today), int(30 * u), INK), pill("Ne restano " + qty_text(r.qty, r.unit), int(30 * u), GREEN)]
    sp = int(16 * u)
    crow = Image.new("RGBA", (sum(c.width for c in chips) + sp * (len(chips) - 1), chips[0].height), (0, 0, 0, 0))
    x = 0
    for c in chips:
        crow.alpha_composite(c, (x, 0))
        x += c.width + sp
    if crow.width > W - 2 * pad:
        crow = scaled(crow, (W - 2 * pad) / crow.width)
    layers.append((crow, int(18 * u)))
    dl = date_line(r)
    if dl:
        layers.append((text_layer([dl], font(int(32 * u), True), (70, 74, 86), "center"), 0))
    total = sum(l.height + g for l, g in layers)
    block = Image.new("RGBA", (W, total), (0, 0, 0, 0))
    y = 0
    for lay, g in layers:
        block.alpha_composite(lay, ((W - lay.width) // 2, y))
        y += lay.height + g
    return block


def story_image(store: Store, r: Rescue, today: date) -> Image.Image:
    return _compose(store, r, 1080, 1920, today)


def post_image(store: Store, r: Rescue, today: date) -> Image.Image:
    return _compose(store, r, 1080, 1350, today)


# ----------------------------------------------------------------- cartellino «Salvami»

A6 = (1240, 1748)                 # 105 x 148 mm a 300 dpi: 4 per foglio A4


def tag_image(store: Store, r: Rescue, today: date) -> Image.Image:
    w, h = A6
    u = w / 1240
    brand, accent = hex_rgb(store.brand_color), hex_rgb(store.accent_color)
    img = Image.new("RGB", (w, h), WHITE)
    d = ImageDraw.Draw(img)
    band = int(h * 0.16)
    d.rectangle((0, 0, w, band), fill=GREEN)
    ft, lt = fit_text("SALVAMI", int(w * 0.6), int(band * 0.8), int(band * 0.62), "display", 1)
    d.text((int(60 * u), band // 2), lt[0], font=ft, fill=WHITE, anchor="lm")
    fs = font(int(34 * u), True)
    d.text((w - int(60 * u), band // 2), "dallo spreco", font=fs, fill=WHITE, anchor="rm")
    pad = int(60 * u)
    y = band + int(56 * u)
    fn, ln = fit_text(r.name, w - 2 * pad, int(250 * u), int(96 * u), True, 2, min_size=int(48 * u))
    nl = text_layer(ln, fn, INK)
    img.paste(nl, (pad, y), nl)
    y += nl.height + int(8 * u)
    if r.description:
        fd, ld = fit_text(r.description, w - 2 * pad, int(70 * u), int(56 * u), False, 1)
        dl_ = text_layer(ld, fd, (90, 94, 106))
        img.paste(dl_, (pad, y), dl_)
    pct = discount_pct(r)
    if pct:
        burst = discount_burst(pct, int(330 * u), accent)
        img.paste(burst, (w - pad - burst.width + int(20 * u), int(h * 0.36)), burst)
    price = price_block(r.rescue_price_cents, int(h * 0.2), brand)
    if price.width > w - 2 * pad:
        price = scaled(price, (w - 2 * pad) / price.width)
    py = int(h * 0.58)
    img.paste(price, (pad, py), price)
    if r.unit == "kg" and "kg" not in (r.description or "").lower():
        d.text((pad + price.width + int(20 * u), py + int(20 * u)), "al kg", font=font(int(46 * u), True), fill=INK)
    old = old_price_line(r.price_cents, int(56 * u), (90, 94, 106))
    img.paste(old, (pad, py + price.height + int(24 * u)), old)
    dl = date_line(r)
    foot = int(h * 0.12)
    if dl:
        d.text((pad, h - foot - int(56 * u)), dl, font=font(int(44 * u), True), fill=INK, anchor="lm")
    d.rectangle((0, h - foot, w, h), fill=mix(GREEN, WHITE, 0.88))
    d.text((pad, h - foot // 2), "Aiutaci a non sprecare", font=font(int(40 * u), True), fill=GREEN, anchor="lm")
    d.text((w - pad, h - foot // 2), store.name[:30], font=font(int(32 * u)), fill=(90, 94, 106), anchor="rm")
    return img


def tags_pdf(store: Store, rescues: list[Rescue], out: Path, today: date) -> Path:
    """Cartellini A6, 4 per foglio A4, con le linee di taglio."""
    if not rescues:
        raise RescueError("Nessun prodotto in Salvaspreco da stampare.")
    W, H = 2480, 3508
    tw, th = W // 2, H // 2
    pages = []
    for start in range(0, len(rescues), 4):
        page = Image.new("RGB", (W, H), WHITE)
        for k, r in enumerate(rescues[start:start + 4]):
            tag = tag_image(store, r, today)
            tag.thumbnail((tw - 40, th - 40), Image.LANCZOS)
            page.paste(tag, ((k % 2) * tw + (tw - tag.width) // 2, (k // 2) * th + (th - tag.height) // 2))
        d = ImageDraw.Draw(page)
        for x in range(0, W, 28):
            d.line((x, th, x + 14, th), fill=(170, 170, 170), width=2)
        for y in range(0, H, 28):
            d.line((tw, y, tw, y + 14), fill=(170, 170, 170), width=2)
        pages.append(page)
    out.parent.mkdir(parents=True, exist_ok=True)
    pages[0].save(out, "PDF", resolution=300, save_all=True, append_images=pages[1:])
    return out


# ----------------------------------------------------------------- creare, chiudere

@dataclass
class RescueIn:
    name: str
    description: str = ""
    reason: str = "scadenza"
    date_kind: str = ""
    expires_on: date | None = None
    until: date | None = None
    qty: float = 1
    unit: str = "pezzi"
    unit_weight_g: int | None = None
    price_cents: int = 0
    rescue_price_cents: int | None = None
    offer_id: int | None = None


def _folder(data_dir: Path) -> Path:
    p = Path(data_dir) / "rescues"
    p.mkdir(parents=True, exist_ok=True)
    return p


def validate(data: RescueIn, today: date) -> list[str]:
    if len(data.name.strip()) < 2:
        raise RescueError("Scrivi il nome del prodotto.")
    if data.reason not in REASONS:
        raise RescueError("Motivo non valido.")
    if data.unit not in UNITS:
        raise RescueError("Unità non valida: pezzi o kg.")
    if not (0 < data.qty <= 10000):
        raise RescueError("Indica quanti pezzi (o chili) ci sono.")
    if data.price_cents <= 0:
        raise RescueError("Scrivi il prezzo normale del prodotto.")
    if data.rescue_price_cents is not None and not (0 < data.rescue_price_cents < data.price_cents):
        raise RescueError("Il prezzo Salvaspreco deve essere più basso del prezzo normale.")
    if data.until and data.until < today:
        raise RescueError("L'ultimo giorno dell'offerta non può essere nel passato.")
    if data.date_kind == "scadenza" and data.expires_on and data.until and data.until > data.expires_on:
        raise RescueError("L'offerta non può durare oltre la data di scadenza.")
    return check_sellable(data.date_kind, data.expires_on, today)


def create(session: Session, store: Store, data: RescueIn, data_dir: Path, today: date,
           photo: Image.Image | None = None, offer: Offer | None = None) -> tuple[Rescue, list[str]]:
    notes = validate(data, today)
    pct = suggest_discount(data.reason, data.date_kind, data.expires_on, today)
    r = Rescue(store_id=store.id, offer_id=offer.id if offer is not None else data.offer_id, day=today,
               name=data.name.strip()[:200], description=data.description.strip()[:200], reason=data.reason,
               date_kind=data.date_kind, expires_on=data.expires_on,
               until=data.until or (data.expires_on if data.date_kind == "scadenza" and data.expires_on
                                    and data.expires_on > today and data.reason == "scadenza" else today),
               qty=data.qty, unit=data.unit,
               unit_weight_g=data.unit_weight_g or (unit_weight_g(data.name, data.description) if data.unit == "pezzi" else None),
               price_cents=data.price_cents,
               rescue_price_cents=data.rescue_price_cents or rescue_price(data.price_cents, pct))
    if r.date_kind == "scadenza" and r.expires_on and r.until and r.until > r.expires_on:
        r.until = r.expires_on
    session.add(r)
    session.flush()
    folder = _folder(data_dir)
    if photo is not None:
        p = folder / f"{r.id}_foto.png"
        cut = None
        try:
            from ... import cutout
            if cutout.available():
                cut = cutout.cut(photo, "")
        except Exception:          # lo scontorno è un di più
            cut = None
        (cut or photo.convert("RGB")).save(p)
        r.photo_path = str(p)
    elif offer is not None:
        from .video.service import offer_image
        src = offer_image(offer, cut=True)
        if src and Path(src).exists():
            p = folder / f"{r.id}_foto{Path(src).suffix or '.png'}"
            shutil.copyfile(src, p)
            r.photo_path = str(p)
    render(store, r, data_dir, today)
    session.flush()
    return r, notes


def render(store: Store, r: Rescue, data_dir: Path, today: date) -> None:
    folder = _folder(data_dir)
    story, post = folder / f"{r.id}_storia.jpg", folder / f"{r.id}_post.jpg"
    story_image(store, r, today).save(story, quality=92)
    post_image(store, r, today).save(post, quality=92)
    r.story_path, r.post_path = str(story), str(post)
    r.text, r.short_text = write_texts(store, r, today)


def close(r: Rescue, sold: float) -> Rescue:
    if sold < 0:
        raise RescueError("Il numero di venduti non può essere negativo.")
    if sold > r.qty + 1e-9:
        raise RescueError(f"Hai messo in Salvaspreco {qty_text(r.qty, r.unit)}: i venduti non possono essere di più.")
    r.sold_qty = sold
    r.closed_at = datetime.now(timezone.utc)
    return r


def delete_files(r: Rescue) -> None:
    for p in (r.photo_path, r.story_path, r.post_path):
        if p:
            Path(p).unlink(missing_ok=True)


# ----------------------------------------------------------------- il conto del mese

def month_rescues(session: Session, store: Store, year: int, month: int) -> list[Rescue]:
    first, last = date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])
    return list(session.scalars(select(Rescue).where(Rescue.store_id == store.id, Rescue.day >= first,
                                                     Rescue.day <= last).order_by(Rescue.day.desc(), Rescue.id.desc())))


def month_stats(session: Session, store: Store, year: int, month: int) -> dict:
    rs = month_rescues(session, store, year, month)
    closed = [r for r in rs if r.closed_at is not None]
    pieces_sold = sum(r.sold_qty or 0 for r in closed if r.unit == "pezzi")
    kg_known = [saved_kg(r) for r in closed]
    kg = sum(k for k in kg_known if k)
    revenue = sum(int(round((r.sold_qty or 0) * r.rescue_price_cents)) for r in closed)
    offered = sum(r.qty for r in closed)
    sold = sum(r.sold_qty or 0 for r in closed)
    best = max(closed, key=lambda r: (r.sold_qty or 0) * r.rescue_price_cents, default=None)
    reasons: dict[str, int] = {}
    for r in rs:
        reasons[r.reason] = reasons.get(r.reason, 0) + 1
    return {
        "month": f"{year:04d}-{month:02d}", "label": f"{MONTHS[month - 1]} {year}",
        "products": len(rs), "closed": len(closed), "open": len(rs) - len(closed),
        "pieces_sold": round(pieces_sold, 1), "kg_saved": round(kg, 1),
        "kg_unknown": sum(1 for k in kg_known if k is None),
        "revenue_cents": revenue, "revenue": format_eur(revenue),
        "sell_through": round(sold * 100 / offered) if offered else None,
        "best": product_label(best) if best is not None and (best.sold_qty or 0) > 0 else "",
        "reasons": reasons,
    }


def impact_headline(stats: dict) -> tuple[str, str]:
    """Il numero grande e la sua etichetta: i chili se si conoscono, altrimenti i prodotti venduti."""
    if stats["kg_saved"] >= 1:
        kg = stats["kg_saved"]
        num = f"{kg:.0f}" if kg >= 10 else f"{kg:.1f}".replace(".", ",")
        return f"{num} kg", "di cibo dallo spreco"
    n = int(round(stats["pieces_sold"]))
    return str(n), ("prodotto dallo spreco" if n == 1 else "prodotti dallo spreco")


def impact_image(store: Store, stats: dict) -> Image.Image:
    W, H = 1080, 1350
    u = 1.0
    brand, accent = hex_rgb(store.brand_color), hex_rgb(store.accent_color)
    img = brand_background(W, H, mix(GREEN, brand, 0.2), accent, u)
    d = ImageDraw.Draw(img)
    fg = WHITE
    pad = 72
    y = 90
    logo = logo_image(store.logo_path or None, 320, 110, mix(GREEN, brand, 0.2))
    if logo is not None:
        img.alpha_composite(logo, ((W - logo.width) // 2, y))
        y += logo.height + 50
    else:
        fs, ls = fit_text(store.name, W - 2 * pad, 70, 46, True, 1)
        d.text((W // 2, y + 30), ls[0], font=fs, fill=fg, anchor="mm")
        y += 110
    badge = pill("SALVASPRECO", 34, WHITE, GREEN)
    img.alpha_composite(badge, ((W - badge.width) // 2, y))
    y += badge.height + 60
    ft, lt = fit_text(f"A {stats['label'].split()[0]} abbiamo salvato", W - 2 * pad, 200, 78, "display", 2)
    tl = text_layer(lt, ft, fg, "center")
    img.alpha_composite(tl, ((W - tl.width) // 2, y))
    y += tl.height + 30
    num, label = impact_headline(stats)
    fbig, lbig = fit_text(num, W - 2 * pad, 300, 260, "display", 1)
    big = text_layer(lbig, fbig, accent if accent != brand else WHITE, "center")
    img.alpha_composite(big, ((W - big.width) // 2, y))
    y += big.height + 10
    fl, ll = fit_text(label, W - 2 * pad, 120, 56, True, 2)
    lab = text_layer(ll, fl, fg, "center")
    img.alpha_composite(lab, ((W - lab.width) // 2, y))
    y += lab.height + 60
    n = stats["products"]
    facts = [f"{n} {'prodotto' if n == 1 else 'prodotti'} in offerta lampo invece che nella spazzatura"]
    for t in facts:
        fs, ls = fit_text(t, W - 2 * pad, 120, 38, False, 2)
        lay = text_layer(ls, fs, mix(fg, brand, 0.12), "center")
        img.alpha_composite(lay, ((W - lay.width) // 2, y))
        y += lay.height + 16
    fth, lth = fit_text("Grazie a chi li ha scelti.", W - 2 * pad, 90, 52, "display", 1)
    d.text((W // 2, H - 150), lth[0], font=fth, fill=fg, anchor="mm")
    where = ", ".join(x for x in (store.address, store.city) if x) or store.name
    fw, lw = fit_text(where, W - 2 * pad, 50, 32, False, 1)
    d.text((W // 2, H - 80), lw[0], font=fw, fill=mix(fg, brand, 0.2), anchor="mm")
    return img.convert("RGB")


def impact_text(store: Store, stats: dict) -> str:
    tone = store.tone or "familiare"
    emoji = tone in ("familiare", "giovane")
    num, label = impact_headline(stats)
    month = stats["label"].split()[0]
    lines = [(("💚 " if emoji else "") + f"A {month} abbiamo salvato {num} {label}.").strip(), ""]
    lines.append(f"Ogni giorno mettiamo in offerta lampo i prodotti vicini alla scadenza, la frutta molto matura e "
                 f"il pane di fine giornata: {stats['products']} prodotti questo mese, invece che nella spazzatura.")
    lines.append("Grazie a chi li ha scelti: un buon prezzo per voi, meno spreco per tutti.")
    lines.append("Seguiteci per scoprire ogni giorno il Salvaspreco.")
    lines += ["", "#salvaspreco #antispreco #nonsprecare"]
    return "\n".join(lines)
