"""Avvisi di servizio: orari festivi, chiusure, cambi d'orario, lavori. Si scrivono una volta, Promovo prepara tutto.

Come gli avvisi dei trasporti pubblici, che arrivano uguali su ogni canale: dallo stesso avviso Promovo prepara il
cartello A4 per la porta, il post e la storia, il messaggio per lo stato WhatsApp, la schermata per gli schermi del
negozio e il testo con gli orari speciali per la scheda Google. Per le catene la sede scrive l'avviso una volta e lo
manda a tutti i punti vendita.

Le festività nazionali sono già nel calendario (compreso il 4 ottobre, San Francesco, festa nazionale dal 2026,
legge 151/2025); la festa del patrono del comune il negozio la aggiunge da sé.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from PIL import Image, ImageDraw

from ..models import Notice, Store
from .content.calendar import easter
from .video.render import (INK, WHITE, brand_background, fit_text, font, hex_rgb, logo_image, pill,
                           readable_on_paper, text_layer, text_on)

KINDS = {"festivo": "Orari festivi", "chiusura": "Chiusura", "orari": "Nuovi orari", "lavori": "Lavori in corso",
         "altro": "Avviso"}
DAYS = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
MONTHS = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre",
          "novembre", "dicembre"]


class NoticeError(ValueError):
    pass


# ----------------------------------------------------------------- calendario

def holidays(year: int) -> list[tuple[date, str]]:
    """Le festività nazionali italiane dell'anno (con Pasqua e Pasquetta)."""
    e = easter(year)
    out = [(date(year, 1, 1), "Capodanno"), (date(year, 1, 6), "Epifania"), (e, "Pasqua"),
           (e + timedelta(days=1), "Lunedì dell'Angelo (Pasquetta)"), (date(year, 4, 25), "Festa della Liberazione"),
           (date(year, 5, 1), "Festa dei Lavoratori"), (date(year, 6, 2), "Festa della Repubblica"),
           (date(year, 8, 15), "Ferragosto"), (date(year, 11, 1), "Ognissanti"),
           (date(year, 12, 8), "Immacolata Concezione"), (date(year, 12, 25), "Natale"),
           (date(year, 12, 26), "Santo Stefano")]
    if year >= 2026:
        out.append((date(year, 10, 4), "San Francesco d'Assisi"))
    # vigilie in cui molti negozi cambiano orario
    out += [(date(year, 12, 24), "Vigilia di Natale"), (date(year, 12, 31), "San Silvestro")]
    return sorted(out)


TITLES = {"Capodanno": "Orari di Capodanno", "Epifania": "Orari dell'Epifania", "Pasqua": "Orari di Pasqua",
          "Lunedì dell'Angelo (Pasquetta)": "Orari di Pasquetta", "Festa della Liberazione": "Orari del 25 aprile",
          "Festa dei Lavoratori": "Orari del 1° maggio", "Festa della Repubblica": "Orari del 2 giugno",
          "Ferragosto": "Orari di Ferragosto", "Ognissanti": "Orari di Ognissanti",
          "Immacolata Concezione": "Orari dell'Immacolata", "Natale": "Orari di Natale",
          "Santo Stefano": "Orari di Santo Stefano", "San Francesco d'Assisi": "Orari del 4 ottobre",
          "Vigilia di Natale": "Orari della Vigilia di Natale", "San Silvestro": "Orari di San Silvestro"}


def upcoming(today: date, days: int = 45) -> list[dict]:
    end = today + timedelta(days=days)
    out = []
    for y in (today.year, today.year + 1):
        for d, name in holidays(y):
            if today <= d <= end:
                out.append({"date": d.isoformat(), "name": name, "label": day_label(d),
                            "title": TITLES.get(name, f"Orari di {name}")})
    return out


def day_label(d: date) -> str:
    return f"{DAYS[d.weekday()]} {d.day} {MONTHS[d.month - 1]}"


def when(n: Notice) -> str:
    if n.date_from == n.date_to:
        return day_label(n.date_from).capitalize()
    if n.date_from.month == n.date_to.month:
        return f"Da {DAYS[n.date_from.weekday()]} {n.date_from.day} a {DAYS[n.date_to.weekday()]} {n.date_to.day} " \
               f"{MONTHS[n.date_to.month - 1]}"
    return f"Da {day_label(n.date_from)} a {day_label(n.date_to)}"


def hours_text(n: Notice) -> str:
    return "Chiuso" if n.closed else (n.hours or "")


# ----------------------------------------------------------------- validazione

@dataclass
class NoticeIn:
    kind: str
    title: str
    date_from: date
    date_to: date
    hours: str = ""
    closed: bool = False
    message: str = ""


def validate(d: NoticeIn, today: date) -> NoticeIn:
    if d.kind not in KINDS:
        raise NoticeError("Tipo di avviso non valido.")
    d.title = " ".join(d.title.split())[:120]
    d.hours = " ".join(d.hours.split())[:80]
    d.message = " ".join(d.message.split())[:300]
    if len(d.title) < 3:
        raise NoticeError("Scrivi il titolo dell'avviso (es. «Orari di Natale»).")
    if d.date_to < d.date_from:
        raise NoticeError("L'ultimo giorno viene prima del primo.")
    if d.date_to < today:
        raise NoticeError("L'avviso riguarda giorni già passati.")
    if (d.date_to - d.date_from).days > 92:
        raise NoticeError("Un avviso può durare al massimo tre mesi.")
    if not d.closed and not d.hours and d.kind in ("festivo", "orari"):
        raise NoticeError("Scrivi gli orari (es. «8:00 – 13:00») oppure segna «chiuso».")
    return d


# ----------------------------------------------------------------- testi

def texts(store: Store, n: Notice) -> dict:
    tone = store.tone or "familiare"
    emoji = tone in ("familiare", "giovane")
    voi = tone != "giovane"
    w = when(n)
    if n.closed:
        core = f"{w}: il negozio resta chiuso."
    elif n.hours:
        core = f"{w}: aperti {n.hours}."
    else:
        core = f"{w}."
    lines = [(("📢 " if emoji else "") + n.title).strip(), "", core]
    if n.message:
        lines.append(n.message)
    if n.kind in ("festivo", "chiusura"):
        lines.append("Organizzate la spesa per tempo: vi aspettiamo!" if voi else "Organizza la spesa per tempo: ti aspettiamo!")
    where = ", ".join(x for x in (store.address, store.city) if x)
    if where:
        lines += ["", ("📍 " if emoji else "") + f"{store.name} · {where}"]
    post = "\n".join(lines)
    status = f"{n.title}: {core[0].lower() + core[1:]}" + (f" {n.message}" if n.message else "") + f" — {store.name}"
    days = []
    d = n.date_from
    while d <= n.date_to and len(days) < 31:
        days.append(f"{d.day:02d}/{d.month:02d}/{d.year}: {'chiuso' if n.closed else (n.hours or 'orario normale')}")
        d += timedelta(days=1)
    google = ("Scheda Google (Google Business Profile) → Modifica profilo → Orari → Orari speciali. Inserisci:\n"
              + "\n".join("• " + x for x in days)
              + "\n\nTesto per l'aggiornamento (Aggiungi aggiornamento):\n" + core + (f" {n.message}" if n.message else ""))
    return {"post": post, "status": status, "google": google}


# ----------------------------------------------------------------- grafiche

def _block(store: Store, n: Notice, W: int, H: int, dark: bool) -> Image.Image:
    """Il cuore dell'avviso: tipo, titolo, quando, orari (grandi), messaggio."""
    u = W / 1080
    brand = hex_rgb(store.brand_color)
    fg = WHITE if dark else INK
    sub = (235, 235, 240) if dark else (70, 74, 86)
    pad = int(70 * u)
    layers = []
    layers.append((pill(KINDS[n.kind].upper(), int(30 * u), WHITE if dark else brand,
                        brand if dark else None), int(30 * u)))
    ft, lt = fit_text(n.title, W - 2 * pad, int(260 * u), int(96 * u), "display", 2)
    layers.append((text_layer(lt, ft, fg, "center"), int(30 * u)))
    fw, lw = fit_text(when(n), W - 2 * pad, int(120 * u), int(54 * u), True, 2)
    layers.append((text_layer(lw, fw, fg, "center"), int(24 * u)))
    hrs = hours_text(n)
    if hrs:
        fh, lh = fit_text(hrs, W - 2 * pad, int(220 * u), int(150 * u), "display", 1)
        col = (255, 220, 120) if dark else readable_on_paper(brand)
        layers.append((text_layer(lh, fh, col, "center"), int(24 * u)))
    if n.message:
        fm, lm = fit_text(n.message, W - 2 * pad, int(200 * u), int(42 * u), False, 4)
        layers.append((text_layer(lm, fm, sub, "center"), 0))
    total = sum(l.height + g for l, g in layers)
    block = Image.new("RGBA", (W, total), (0, 0, 0, 0))
    y = 0
    for lay, g in layers:
        block.alpha_composite(lay, ((W - lay.width) // 2, y))
        y += lay.height + g
    return block


def social_image(store: Store, n: Notice, W: int = 1080, H: int = 1350) -> Image.Image:
    u = W / 1080
    brand, accent = hex_rgb(store.brand_color), hex_rgb(store.accent_color)
    img = brand_background(W, H, brand, accent, u)
    d = ImageDraw.Draw(img)
    logo = logo_image(store.logo_path or None, int(300 * u), int(100 * u), brand)
    top = int(70 * u)
    if logo is not None:
        img.alpha_composite(logo, ((W - logo.width) // 2, top))
        top += logo.height + int(20 * u)
    else:
        fs, ls = fit_text(store.name, W - int(140 * u), int(70 * u), int(46 * u), True, 1)
        d.text((W // 2, top + int(30 * u)), ls[0], font=fs, fill=text_on(brand), anchor="mm")
        top += int(80 * u)
    block = _block(store, n, W, H, True)
    foot = int(130 * u)
    room = H - top - foot
    if block.height > room:
        block = block.resize((int(block.width * room / block.height), room), Image.LANCZOS)
    img.alpha_composite(block, ((W - block.width) // 2, top + (room - block.height) // 2))
    where = ", ".join(x for x in (store.address, store.city) if x) or store.name
    fw, lw = fit_text(where, W - int(140 * u), int(56 * u), int(36 * u), True, 1)
    d.text((W // 2, H - int(70 * u)), lw[0], font=fw, fill=text_on(brand), anchor="mm")
    return img.convert("RGB")


def screen_image(store: Store, n: Notice) -> Image.Image:
    """Schermata 16:9 per gli schermi del negozio."""
    W, H = 1920, 1080
    brand, accent = hex_rgb(store.brand_color), hex_rgb(store.accent_color)
    img = brand_background(W, H, brand, accent, 1.0)
    block = _block(store, n, 1300, H, True)
    if block.height > H - 160:
        block = block.resize((int(block.width * (H - 160) / block.height), H - 160), Image.LANCZOS)
    img.alpha_composite(block, ((W - block.width) // 2, (H - block.height) // 2))
    d = ImageDraw.Draw(img)
    d.text((W // 2, H - 50), store.name, font=font(36, True), fill=text_on(brand), anchor="mm")
    return img.convert("RGB")


def poster_pdf(store: Store, n: Notice, out: Path) -> Path:
    """Il cartello A4 per la porta e la cassa: fondo chiaro, si legge da lontano, stampa bene anche in bianco e nero."""
    W, H = 2480, 3508
    brand = hex_rgb(store.brand_color)
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, W, 360), fill=brand)
    fs, ls = fit_text(store.name, W - 300, 200, 130, "display", 1)
    d.text((W // 2, 180), ls[0], font=fs, fill=text_on(brand), anchor="mm")
    block = _block(store, n, W, H, False)
    room = H - 360 - 420
    if block.height > room:
        block = block.resize((int(block.width * room / block.height), room), Image.LANCZOS)
    img.paste(block, ((W - block.width) // 2, 360 + (room - block.height) // 2), block)
    where = ", ".join(x for x in (store.address, store.city) if x)
    if where:
        fw, lw = fit_text(where, W - 300, 120, 80, True, 1)
        d.text((W // 2, H - 220), lw[0], font=fw, fill=INK, anchor="mm")
    if store.phone:
        d.text((W // 2, H - 110), f"Tel. {store.phone}", font=font(64), fill=(70, 74, 86), anchor="mm")
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PDF", resolution=300)
    return out
