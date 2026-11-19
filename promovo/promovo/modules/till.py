"""Parola alla cassa: sapere quali canali portano davvero clienti in negozio.

Per ogni volantino ogni canale ha la sua parola d'ordine (es. «ARANCIA» su Instagram, «LIMONE» su WhatsApp).
I testi la riportano: «Dì ARANCIA alla cassa: per te il 5% di sconto sulla spesa». Alla cassa si conta:
con il tasto +1 in Promovo, oppure sul foglio stampato (e poi si riportano i numeri). Alla fine del volantino
Promovo dice quale canale ha portato più clienti e dove conviene mettere il tempo la settimana dopo.

- Si contano solo numeri: nessun nome, nessun dato personale dei clienti.
- Il premio lo decide il negozio. Il predefinito è uno sconto: gli sconti sul prezzo non sono «operazioni a premio»
  (DPR 430/2001, art. 6, lett. c). Per omaggi e regali è meglio sentire il commercialista.
- Le parole cambiano a ogni volantino, non ripetono quelle dei volantini precedenti e non coincidono con i prodotti
  in offerta (un cliente che compra mele e dice «MELA» confonderebbe i conti).
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path

from PIL import Image, ImageDraw
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ContentPiece, Flyer, Store, TillCode, TillHit
from .radar.service import tokens
from .video.render import INK, WHITE, fit_text, font, hex_rgb, mix, readable_on_paper

CHANNELS = {"instagram": "Instagram", "facebook": "Facebook", "whatsapp": "WhatsApp", "reel": "Reel e TikTok"}
PIECE_CHANNEL = {"instagram": "instagram", "facebook": "facebook", "reel": "reel"}
WORDS = ["ARANCIA", "LIMONE", "BASILICO", "CILIEGIA", "MANDORLA", "NOCCIOLA", "FRAGOLA", "ALBICOCCA", "MIRTILLO",
         "LAMPONE", "MELOGRANO", "CASTAGNA", "ROSMARINO", "SALVIA", "ORIGANO", "MENTA", "CANNELLA", "VANIGLIA",
         "PISTACCHIO", "SESAMO", "GIRASOLE", "PAPAVERO", "LAVANDA", "MARGHERITA", "TULIPANO", "GELSOMINO",
         "ZAFFERANO", "PEPERONCINO", "MANDARINO", "POMPELMO", "BERGAMOTTO", "CEDRO", "OLIVA", "FICO", "MELONE",
         "ANGURIA", "CAROTA", "ZUCCA", "CARCIOFO", "FINOCCHIO"]
MARK = "alla cassa:"            # riconosce la riga della parola d'ordine nei testi
WEEKDAYS = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"]
MAX_REWARD = 80


# ----------------------------------------------------------------- parole

def _norm(w: str) -> str:
    return next(iter(tokens(w)), w.lower())


def codes_for(session: Session, store: Store, flyer: Flyer) -> dict[str, TillCode]:
    """Le parole d'ordine del volantino, una per canale (create la prima volta, poi sempre le stesse)."""
    have = {c.channel: c for c in session.scalars(select(TillCode).where(TillCode.flyer_id == flyer.id))}
    if len(have) == len(CHANNELS):
        return have
    recent = session.scalars(select(TillCode.word).where(TillCode.store_id == store.id)
                             .order_by(TillCode.id.desc()).limit(4 * len(CHANNELS) * 3)).all()
    on_offer = set()
    for o in flyer.offers:
        on_offer |= tokens(" ".join(x for x in (o.name, o.brand, o.description) if x))
    used = {c.word for c in have.values()}
    pool = [w for w in WORDS if w not in recent and w not in used and _norm(w) not in on_offer]
    if len(pool) < len(CHANNELS):
        pool = [w for w in WORDS if w not in used and _norm(w) not in on_offer]
    start = (flyer.id * 7) % len(pool)            # ogni volantino parte da un punto diverso dell'elenco
    pool = pool[start:] + pool[:start]
    for ch in CHANNELS:
        if ch not in have:
            word = pool.pop(0)
            have[ch] = TillCode(store_id=store.id, flyer_id=flyer.id, channel=ch, word=word)
            session.add(have[ch])
    session.flush()
    return have


def clean_reward(text: str) -> str:
    t = " ".join((text or "").split()).strip().rstrip(".")
    if len(t) < 3:
        raise ValueError("Scrivi cosa ricevono i clienti che dicono la parola (es. «il 5% di sconto sulla spesa»).")
    if len(t) > MAX_REWARD:
        raise ValueError(f"Il premio deve stare in {MAX_REWARD} caratteri.")
    return t


def line_for(store: Store, flyer: Flyer | None, code: TillCode) -> str:
    """La riga da mettere nei testi, nel tono del negozio."""
    tone = store.tone or "familiare"
    until = f" Fino al {flyer.valid_to.day}/{flyer.valid_to.month}." if flyer is not None and flyer.valid_to else ""
    reward = store.till_reward or "un piccolo sconto"
    if tone == "elegante":
        return f"Dite «{code.word}» {MARK} per voi {reward}.{until}"
    lead = "🔑 " if tone in ("familiare", "giovane") else ""
    return f"{lead}Dì «{code.word}» {MARK} per te {reward}.{until}"


def strip(text: str) -> str:
    """Il testo senza la riga della parola d'ordine (per i controlli dei prezzi e per spegnere la funzione)."""
    lines = [ln for ln in (text or "").split("\n") if not (MARK in ln and "«" in ln)]
    out = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", out).strip()


def _insert(body: str, line: str) -> str:
    """Mette la riga prima degli hashtag finali (se ci sono), altrimenti in fondo."""
    body = strip(body)
    parts = body.rstrip().split("\n\n")
    if len(parts) > 1 and parts[-1].lstrip().startswith("#"):
        return "\n\n".join(parts[:-1] + [line, parts[-1]])
    return body.rstrip() + "\n\n" + line


def apply(session: Session, store: Store, flyer: Flyer) -> int:
    """Aggiunge (o toglie, se la funzione è spenta) la parola d'ordine nei testi del volantino."""
    pieces = session.scalars(select(ContentPiece).where(ContentPiece.flyer_id == flyer.id,
                                                        ContentPiece.kind.in_(list(PIECE_CHANNEL)))).all()
    if not pieces:
        return 0
    codes = codes_for(session, store, flyer) if store.till_on else {}
    for p in pieces:
        if store.till_on:
            p.body = _insert(p.body, line_for(store, flyer, codes[PIECE_CHANNEL[p.kind]]))
        else:
            p.body = strip(p.body)
    session.flush()
    return len(pieces)


# ----------------------------------------------------------------- conteggi

def _hit_row(session: Session, code: TillCode, day: date) -> TillHit:
    row = session.scalars(select(TillHit).where(TillHit.code_id == code.id, TillHit.day == day)).first()
    if row is None:
        row = TillHit(code_id=code.id, day=day, count=0)
        session.add(row)
    return row


def add(session: Session, code: TillCode, day: date, delta: int) -> int:
    if delta not in (1, -1):
        raise ValueError("Si conta un cliente alla volta.")
    row = _hit_row(session, code, day)
    row.count = max(0, (row.count or 0) + delta)
    session.flush()
    return row.count


def set_count(session: Session, code: TillCode, day: date, count: int) -> int:
    if not 0 <= count <= 10000:
        raise ValueError("Numero non valido.")
    row = _hit_row(session, code, day)
    row.count = count
    session.flush()
    return row.count


def period(flyer: Flyer, today: date) -> list[date]:
    """I giorni del volantino (al massimo 21), oppure gli ultimi 7 giorni se il volantino non ha date."""
    if flyer.valid_from and flyer.valid_to and flyer.valid_to >= flyer.valid_from:
        n = min((flyer.valid_to - flyer.valid_from).days + 1, 21)
        return [flyer.valid_from + timedelta(days=i) for i in range(n)]
    start = (flyer.created_at.date() if flyer.created_at else today)
    return [start + timedelta(days=i) for i in range(7)]


def results(session: Session, store: Store, flyer: Flyer, today: date) -> dict:
    codes = codes_for(session, store, flyer)
    days = period(flyer, today)
    hits = session.scalars(select(TillHit).where(TillHit.code_id.in_([c.id for c in codes.values()]))).all()
    by = {(h.code_id, h.day): h.count for h in hits}
    rows = []
    for ch, label in CHANNELS.items():
        c = codes[ch]
        counts = [by.get((c.id, d), 0) for d in days]
        extra = sum(n for (cid, d), n in by.items() if cid == c.id and d not in days)   # fuori dalle date
        rows.append({"channel": ch, "label": label, "word": c.word, "code_id": c.id, "counts": counts,
                     "total": sum(counts) + extra, "today": by.get((c.id, today), 0),
                     "line": line_for(store, flyer, c)})
    total = sum(r["total"] for r in rows)
    for r in rows:
        r["share"] = round(r["total"] * 100 / total) if total else 0
    return {"days": [d.isoformat() for d in days], "day_labels": [f"{WEEKDAYS[d.weekday()]} {d.day}" for d in days],
            "rows": rows, "total": total}


def history(session: Session, store: Store, limit: int = 6) -> list[dict]:
    """I totali per canale dei volantini precedenti (i più recenti per primi)."""
    flyer_ids = session.scalars(select(TillCode.flyer_id).where(TillCode.store_id == store.id)
                                .group_by(TillCode.flyer_id).order_by(TillCode.flyer_id.desc()).limit(limit)).all()
    out = []
    for fid in flyer_ids:
        f = session.get(Flyer, fid)
        if f is None:
            continue
        codes = session.scalars(select(TillCode).where(TillCode.flyer_id == fid)).all()
        tot = {}
        for c in codes:
            tot[c.channel] = sum(h.count for h in session.scalars(select(TillHit).where(TillHit.code_id == c.id)))
        out.append({"flyer_id": fid, "title": f.title or "Volantino",
                    "valid_from": f.valid_from.isoformat() if f.valid_from else None,
                    "totals": tot, "total": sum(tot.values())})
    return out


def advice(res: dict, past: list[dict]) -> list[str]:
    """Due o tre consigli concreti, solo dai numeri."""
    rows = sorted(res["rows"], key=lambda r: r["total"], reverse=True)
    total = res["total"]
    if total == 0:
        return ["Ancora nessun cliente contato: ricorda alla cassa di segnare ogni parola detta, anche con il "
                "foglio stampato."]
    tips = []
    best = rows[0]
    if total < 10:
        tips.append(f"Finora {total} {'cliente' if total == 1 else 'clienti'}: i numeri sono ancora pochi per "
                    "decidere, aspetta la fine del volantino.")
    else:
        tips.append(f"{best['label']} porta più clienti alla cassa ({best['total']}, il {best['share']}%): pubblica "
                    f"lì per primo e con più cura.")
    zero = [r["label"] for r in rows if r["total"] == 0]
    if zero and total >= 10:
        tips.append("Nessun cliente da " + ", ".join(zero) + ": controlla che i post siano stati pubblicati, "
                    "oppure sposta lì meno tempo.")
    prev = [p for p in past if p["total"]]
    if prev and total >= 10:
        last = prev[0]["total"]
        if last:
            diff = round((total - last) * 100 / last)
            if abs(diff) >= 10:
                tips.append(f"Rispetto al volantino precedente: {'+' if diff > 0 else ''}{diff}% di clienti con la parola.")
    return tips


# ----------------------------------------------------------------- foglio per la cassa

def sheet_image(store: Store, flyer: Flyer, res: dict) -> Image.Image:
    """Foglio A4 orizzontale da tenere alla cassa: le parole, il premio e le caselle per segnare ogni cliente."""
    W, H = 3508, 2480
    u = W / 3508
    brand = hex_rgb(store.brand_color)
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)
    pad = int(150 * u)
    d.rectangle((0, 0, W, int(300 * u)), fill=brand)
    fg = (255, 255, 255) if sum(brand) < 600 else INK
    d.text((pad, int(150 * u)), "Parola alla cassa", font=font(int(120 * u), "display"), fill=fg, anchor="lm")
    vt = (f"dal {flyer.valid_from.day}/{flyer.valid_from.month} al {flyer.valid_to.day}/{flyer.valid_to.month}"
          if flyer.valid_from and flyer.valid_to else "")
    d.text((W - pad, int(150 * u)), f"{store.name}  {vt}".strip(), font=font(int(60 * u), True), fill=fg, anchor="rm")
    y = int(380 * u)
    f1, l1 = fit_text(f"Se il cliente dice una di queste parole: applica {store.till_reward} e fai un segno "
                      "nella casella del giorno.", W - 2 * pad, int(170 * u), int(64 * u), True, 2)
    for ln in l1:
        d.text((pad, y), ln, font=f1, fill=INK)
        y += int(f1.size * 1.2)
    y += int(50 * u)
    days = res["day_labels"][:14]
    name_w = int(900 * u)
    cell_w = (W - 2 * pad - name_w) // max(1, len(days))
    head_h = int(130 * u)
    row_h = int((H - y - head_h - int(260 * u)) / len(res["rows"]))
    bottom = y + head_h + row_h * len(res["rows"])
    d.rectangle((pad, y, W - pad, y + head_h), fill=mix(brand, WHITE, 0.88))
    fd = font(int(52 * u), True)
    d.text((pad + int(30 * u), y + head_h // 2), "Parola  ·  canale", font=fd, fill=INK, anchor="lm")
    for i, lab in enumerate(days):
        d.text((pad + name_w + i * cell_w + cell_w // 2, y + head_h // 2), lab, font=fd, fill=INK, anchor="mm")
    for k, r in enumerate(res["rows"]):
        yy = y + head_h + k * row_h
        d.text((pad + int(30 * u), yy + row_h * 0.42), r["word"], font=font(int(96 * u), "display"),
               fill=readable_on_paper(brand), anchor="lm")
        d.text((pad + int(30 * u), yy + row_h * 0.75), r["label"], font=font(int(44 * u)), fill=(100, 104, 116), anchor="lm")
        d.line((pad, yy, W - pad, yy), fill=(200, 200, 200), width=3)
    for i in range(len(days) + 1):
        x = pad + name_w + i * cell_w
        d.line((x, y, x, bottom), fill=(200, 200, 200), width=3)
    d.rectangle((pad, y, W - pad, bottom), outline=(150, 150, 150), width=4)
    fo = font(int(44 * u))
    d.text((pad, H - int(150 * u)), "A fine giornata (o a fine volantino) riporta i numeri in Promovo: «Alla cassa» → "
           "tocca il numero del giorno.", font=fo, fill=(90, 94, 106), anchor="lm")
    d.text((pad, H - int(85 * u)), "Si contano solo i numeri: niente nomi, niente dati dei clienti.", font=fo,
           fill=(90, 94, 106), anchor="lm")
    return img


def sheet_pdf(store: Store, flyer: Flyer, res: dict, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet_image(store, flyer, res).save(out, "PDF", resolution=300)
    return out
