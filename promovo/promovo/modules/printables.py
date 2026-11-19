"""Materiali per il negozio vero (non solo per i social), dalla stessa lettura del volantino.

- Cartellini promozionali per gli scaffali (A4, 8 per foglio, con le linee di taglio): nome, formato,
  prezzo in offerta, prezzo precedente barrato e sconto (gli stessi controllati nel passo 1, anche dall'agente
  Omnibus), prezzo al kg / al litro (obbligatorio sui cartellini, Codice del Consumo artt. 13-17) e validità.
- Locandina per la vetrina (A4 o A3): le offerte in evidenza, indirizzo, orari e QR code.
- Piano della settimana per il calendario del telefono (file .ics): un promemoria per ogni pubblicazione.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from PIL import Image, ImageDraw

from ..models import Flyer, Offer, Store
from ..money import format_eur
from .content.service import featured_offers, validity_text
from .radar.service import per_unit
from .video.render import (INK, brand_background, discount_burst, fit_text, font, hex_rgb, logo_image, old_price_line,
                           paste, price_block, qr_image, readable_on_paper, soft_background, text_layer, text_on)
from .video.service import store_contacts, to_video_offer

DPI = 300
A4 = (2480, 3508)                          # 210 x 297 mm a 300 dpi


def unit_price_line(o: Offer) -> str:
    """Prezzo per unità di misura, come va scritto sul cartellino."""
    if o.unit_price_text:
        return o.unit_price_text
    pu = per_unit(o)
    if pu is None:
        return ""
    cents, label = pu
    if label == "al pezzo" and abs(cents - o.price_cents) < 1:
        return ""
    return f"{format_eur(int(round(cents)))} {label}"


def _until(flyer: Flyer) -> str:
    return f"fino al {flyer.valid_to.day}/{flyer.valid_to.month}" if flyer.valid_to else "offerta"


def shelf_tag(store: Store, flyer: Flyer, o: Offer, w: int, h: int) -> Image.Image:
    """Un cartellino promozionale da scaffale."""
    brand, accent = hex_rgb(store.brand_color), hex_rgb(store.accent_color)
    img = Image.new("RGB", (w, h), (255, 255, 255))
    d = ImageDraw.Draw(img)
    u = w / 1240
    band = int(h * 0.19)
    d.rectangle((0, 0, w, band), fill=brand)
    fg = text_on(brand)
    ft, lt = fit_text("OFFERTA", int(w * 0.5), int(band * 0.8), int(band * 0.62), "display", 1)
    d.text((int(44 * u), band // 2), lt[0], font=ft, fill=fg, anchor="lm")
    fv, lv = fit_text(_until(flyer), int(w * 0.42), int(band * 0.6), int(band * 0.36), True, 1)
    d.text((w - int(44 * u), band // 2), lv[0], font=fv, fill=fg, anchor="rm")
    pad = int(44 * u)
    y = band + int(30 * u)
    name = " ".join(x for x in (o.brand, o.name) if x)
    fn, ln = fit_text(name, w - 2 * pad, int(h * 0.26), int(78 * u), True, 2, min_size=int(36 * u))
    layer = text_layer(ln, fn, INK)
    img.paste(layer, (pad, y), layer)
    y += layer.height + int(6 * u)
    if o.description:
        fd, ld = fit_text(o.description, w - 2 * pad, int(60 * u), int(46 * u), False, 1)
        dl = text_layer(ld, fd, (90, 94, 106))
        img.paste(dl, (pad, y), dl)
    # prezzo grande in basso a destra, prezzo precedente e sconto a sinistra
    price = price_block(o.price_cents, int(h * 0.34), brand)
    if price.width > w * 0.62:
        price = price.resize((int(w * 0.62), int(price.height * w * 0.62 / price.width)), Image.LANCZOS)
    px, py = w - pad - price.width, h - int(h * 0.12) - price.height
    img.paste(price, (px, py), price)
    if o.old_price_cents:
        old = old_price_line(o.old_price_cents, int(44 * u), (90, 94, 106))
        img.paste(old, (pad, py + price.height - old.height - int(8 * u)), old)
        pct = o.discount_percent
        if pct:
            burst = discount_burst(pct, int(h * 0.27), accent)
            img.paste(burst, (pad - int(8 * u), py - int(h * 0.06)), burst)
    unit = unit_price_line(o)
    foot = int(h * 0.12)
    d.rectangle((0, h - foot, w, h), fill=(244, 242, 238))
    fu = font(int(38 * u), True)
    if unit:
        d.text((pad, h - foot // 2), unit, font=fu, fill=INK, anchor="lm")
    fs = font(int(30 * u))
    d.text((w - pad, h - foot // 2), store.name[:40], font=fs, fill=(110, 112, 120), anchor="rm")
    return img


def shelf_tags_pdf(store: Store, flyer: Flyer, out: Path, offers: list[Offer] | None = None) -> Path:
    """Cartellini di tutte le offerte, 8 per foglio A4, con le linee di taglio tratteggiate."""
    offers = list(offers if offers is not None else flyer.offers)
    W, H = A4
    cols, rows = 2, 4
    tw, th = W // cols, H // rows
    pages = []
    for start in range(0, len(offers), cols * rows):
        page = Image.new("RGB", (W, H), (255, 255, 255))
        for k, o in enumerate(offers[start:start + cols * rows]):
            c, r = k % cols, k // cols
            margin = 18
            tag = shelf_tag(store, flyer, o, tw - 2 * margin, th - 2 * margin)
            page.paste(tag, (c * tw + margin, r * th + margin))
        d = ImageDraw.Draw(page)
        for x in range(0, W, 28):                          # linee di taglio
            for r in range(1, rows):
                d.line((x, r * th, x + 14, r * th), fill=(170, 170, 170), width=2)
        for y in range(0, H, 28):
            d.line((tw, y, tw, y + 14), fill=(170, 170, 170), width=2)
        pages.append(page)
    if not pages:
        raise ValueError("Nessuna offerta per i cartellini.")
    out.parent.mkdir(parents=True, exist_ok=True)
    pages[0].save(out, "PDF", resolution=DPI, save_all=True, append_images=pages[1:])
    return out


def poster(store: Store, flyer: Flyer, size: str = "A4") -> Image.Image:
    """Locandina per la vetrina con le offerte in evidenza (200 dpi)."""
    W, H = (1654, 2339) if size == "A4" else (2339, 3307)
    u = W / 1080
    brand, accent = hex_rgb(store.brand_color), hex_rgb(store.accent_color)
    img = soft_background(W, H, brand, u)
    d = ImageDraw.Draw(img)
    fg = text_on(brand)
    x, y = int(56 * u), int(46 * u)
    logo = logo_image(store.logo_path or None, int(320 * u), int(100 * u), brand)
    # la fascia colorata è alta quanto serve: logo, titolo e date restano dentro
    need = y + (logo.height + int(18 * u) if logo is not None else 0) + int(76 * u * 1.2) + int(48 * u) + int(40 * u)
    head_h = max(int(H * 0.18), need)
    img.alpha_composite(brand_background(W, head_h, brand, accent, u), (0, 0))
    if logo is not None:
        img.alpha_composite(logo, (x, y))
        y += logo.height + int(18 * u)
    ft, lt = fit_text("Le offerte della settimana", W - 2 * x, int(90 * u), int(76 * u), "display", 1)
    d.text((x, y), lt[0], font=ft, fill=fg)
    y += int(ft.size * 1.2)
    vt = validity_text(flyer)
    if vt:
        fs, ls = fit_text(vt.capitalize(), W - 2 * x, int(48 * u), int(38 * u), True, 1)
        d.text((x, y), ls[0], font=fs, fill=fg)
    from .graphics.service import _card, _shadowed
    offers = [to_video_offer(o) for o in featured_offers(flyer, 6)]
    cols, rows = 2, 3
    gap = int(28 * u)
    top, bottom = head_h + gap, H - int(H * 0.13)
    cw = (W - 2 * int(44 * u) - gap) // cols
    ch = (bottom - top - gap * (rows - 1)) // rows
    for i, o in enumerate(offers[:cols * rows]):
        c, r = i % cols, i // cols
        card = _shadowed(_card(o, cw, ch, brand, accent, u), u)
        paste(img, card, int(44 * u) + c * (cw + gap) + cw / 2 - card.width / 2,
              top + r * (ch + gap) + ch / 2 - card.height / 2)
    # piede: dove, orari, QR
    foot_top = H - int(H * 0.11)
    lines, link, label = store_contacts(store)
    where = ", ".join(z for z in (store.address, store.city) if z) or store.name
    qsz = int(H * 0.09)
    qr = qr_image(link, qsz) if link else None
    textw = W - 2 * int(44 * u) - (qsz + int(30 * u) if qr is not None else 0)
    fw, lw = fit_text(where, textw, int(56 * u), int(40 * u), True, 1)
    d.text((int(44 * u), foot_top + int(10 * u)), lw[0], font=fw, fill=readable_on_paper(brand))
    if lines:
        fl, ll = fit_text("  ·  ".join(lines), textw, int(50 * u), int(30 * u), False, 1)
        d.text((int(44 * u), foot_top + int(70 * u)), ll[0], font=fl, fill=(80, 84, 96))
    fo, lo = fit_text("Offerte valide fino a esaurimento scorte. Le foto sono indicative.", textw, int(40 * u),
                      int(22 * u), False, 1)
    d.text((int(44 * u), foot_top + int(120 * u)), lo[0], font=fo, fill=(120, 122, 130))
    if qr is not None:
        img.paste(qr, (W - int(44 * u) - qr.width, foot_top), qr if qr.mode == "RGBA" else None)
        if label:
            fq = font(int(20 * u), True)
            d.text((W - int(44 * u) - qr.width / 2, foot_top + qr.height + int(16 * u)), label, font=fq,
                   fill=INK, anchor="mm")
    return img.convert("RGB")


def poster_pdf(store: Store, flyer: Flyer, out: Path, size: str = "A4") -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    poster(store, flyer, size).save(out, "PDF", resolution=200)
    return out


def plan_ics(store: Store, items: list[dict]) -> str:
    """Il piano della settimana come calendario (Google Calendar, iPhone, Outlook): promemoria all'ora giusta."""
    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace(";", r"\;").replace(",", r"\,").replace("\n", r"\n")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Promovo//Piano della settimana//IT", "CALSCALE:GREGORIAN",
           "METHOD:PUBLISH", f"X-WR-CALNAME:{esc('Promovo · ' + store.name)}"]
    for k, it in enumerate(items):
        try:
            d = date.fromisoformat(it["date"])
        except (KeyError, ValueError):
            continue
        out += ["BEGIN:VEVENT", f"UID:promovo-{store.id}-{d:%Y%m%d}-{k}@promovo", f"DTSTAMP:{stamp}"]
        if it.get("time"):
            hh, mm = (it["time"].split(":") + ["0"])[:2]
            start = datetime(d.year, d.month, d.day, int(hh), int(mm))
            out += [f"DTSTART;TZID=Europe/Rome:{start:%Y%m%dT%H%M%S}",
                    f"DTEND;TZID=Europe/Rome:{start + timedelta(minutes=15):%Y%m%dT%H%M%S}"]
        else:
            out += [f"DTSTART;VALUE=DATE:{d:%Y%m%d}", f"DTEND;VALUE=DATE:{d + timedelta(days=1):%Y%m%d}"]
        out += [f"SUMMARY:{esc('Pubblica: ' + it.get('where', ''))}", f"DESCRIPTION:{esc(it.get('what', ''))}"]
        if it.get("time"):
            out += ["BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{esc(it.get('where', 'Promovo'))}",
                    "TRIGGER:-PT10M", "END:VALARM"]
        out.append("END:VEVENT")
    out.append("END:VCALENDAR")
    return "\r\n".join(out) + "\r\n"
