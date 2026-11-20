"""Correttore del volantino: controlla la bozza prima che vada in stampa.

Un errore nel volantino stampato costa caro: il negozio deve vendere al prezzo sbagliato o ristampare, e rischia
sanzioni. Il correttore legge la bozza (lo stesso lettore di Promovo) e segnala, offerta per offerta:

- prezzo al kg / al litro mancante o sbagliato. Va indicato anche nella pubblicità che riporta il prezzo
  (Direttiva 98/6/CE art. 3; Codice del Consumo artt. 13-17); non serve quando coincide con il prezzo di vendita;
- sconto stampato («-30%») diverso da quello che risulta dai prezzi;
- prezzo barrato più basso o uguale al prezzo in offerta; prezzo barrato non conforme alla regola dei 30 giorni
  (Omnibus, art. 17-bis Codice del Consumo), con i volantini del negozio già caricati;
- probabili refusi: lo stesso prodotto 4 o più volte più caro o più economico che nei volantini precedenti;
- lo stesso prodotto due volte con prezzi diversi; formato mancante sui prodotti confezionati;
- date mancanti o incoerenti; prezzi letti con incertezza, da guardare sulla bozza.

Promovo non cambia niente da solo e non decide i prezzi: segnala, e corregge il grafico. I controlli sul testo
stampato (sconto e prezzo al kg) si fanno sui PDF con il testo; sui volantini fatti di immagini si usano i dati
letti.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Flyer, FlyerStatus, Offer, Store
from ..money import format_eur
from .radar.service import per_unit, quantity, similarity

SEVERITY = {"err": "Da correggere", "warn": "Da controllare", "info": "Nota"}
LOOSE = {"frutta e verdura", "carne", "pesce", "salumi e formaggi", "pane e forno"}   # spesso venduti a peso
UNIT_RE = re.compile(r"(?:€\s*\d+[.,]\d{2}\s*(?:/|al|al\s+)\s*(kg|l|lt|litro|chilo)|(?:/|al)\s*(kg|l|lt|litro)\b"
                     r"|prezzo\s+al\s+(kg|litro))", re.IGNORECASE)
PCT_RE = re.compile(r"-\s?(\d{1,2})\s?%")
_UNIT_AFTER = re.compile(r"(?:al\s*(?:kg|chilo|litro|lt|l)\b|€\s*/\s*(?:kg|l)\b|/\s*(?:kg|l)\b)\s*[:=]?\s*€?\s*(\d{1,3})[,.\s](\d{2})\b",
                         re.IGNORECASE)
_UNIT_BEFORE = re.compile(r"(\d{1,3})[,.](\d{2})\s*€?\s*(?:/|al)\s*(?:kg|chilo|litro|lt|l)\b", re.IGNORECASE)


def unit_prices(text: str) -> list[int]:
    """I prezzi al kg / al litro stampati («al kg 1,58», «€ 1,58/kg», «1,58 € al kg»), in centesimi."""
    t = (text or "").replace("\n", " ")
    out = [int(a) * 100 + int(b) for a, b in _UNIT_AFTER.findall(t)]
    out += [int(a) * 100 + int(b) for a, b in _UNIT_BEFORE.findall(t)]
    return out


@dataclass
class Finding:
    severity: str          # err | warn | info
    code: str
    message: str
    fix: str = ""
    offer_id: int | None = None
    offer: str = ""
    page: int | None = None

    def as_dict(self) -> dict:
        return {**asdict(self), "severity_label": SEVERITY[self.severity]}


def _label(o: Offer) -> str:
    return " ".join(x for x in (o.brand, o.name, o.description) if x)


def _box_text(doc, o: Offer) -> str | None:
    """Il testo stampato dentro il riquadro dell'offerta (None se la pagina non ha testo)."""
    if doc is None or not o.bbox or len(o.bbox) != 4:
        return None
    try:
        page = doc[o.page - 1]
    except (IndexError, ValueError):
        return None
    if not page.get_text("text").strip():
        return None
    import pymupdf
    w, h = page.rect.width, page.rect.height
    x0, y0, x1, y1 = o.bbox
    pad = 0.01
    rect = pymupdf.Rect(max(0, x0 - pad) * w, max(0, y0 - pad) * h, min(1, x1 + pad) * w, min(1, y1 + pad) * h)
    return page.get_text("text", clip=rect)


def _needs_unit_price(o: Offer) -> tuple[float, str] | None:
    """Prezzo per unità che dovrebbe comparire (None se non serve: venduto al kg, al pezzo o formato ignoto)."""
    text = " ".join(x for x in (o.name, o.description) if x).lower()
    if re.search(r"\bal\s*(kg|chilo|litro|l)\b", text):
        return None
    q = quantity(o.description or "") or quantity(o.name)
    if q is None or q.kind not in ("massa", "volume") or q.amount <= 0:
        return None
    if abs(q.amount - 1000) < 1:              # 1 kg o 1 litro: il prezzo al kg coincide con il prezzo
        return None
    pu = per_unit(o)
    return pu


def check(session: Session, store: Store, flyer: Flyer, today: date | None = None) -> dict:
    today = today or date.today()
    out: list[Finding] = []
    offers = list(flyer.offers)
    doc = None
    try:
        import pymupdf
        if flyer.pdf_path and Path(flyer.pdf_path).exists():
            doc = pymupdf.open(flyer.pdf_path)
    except Exception:
        doc = None
    text_pages = 0
    try:
        # ------------------------------------------------ date
        if not flyer.valid_from or not flyer.valid_to:
            out.append(Finding("warn", "date_mancanti", "Le date di validità non sono state trovate nella bozza.",
                               "Scrivi in modo chiaro «dal … al …» in prima pagina."))
        elif flyer.valid_to < flyer.valid_from:
            out.append(Finding("err", "date_invertite", f"La fine ({flyer.valid_to:%d/%m}) viene prima dell'inizio "
                               f"({flyer.valid_from:%d/%m}).", "Controlla le date in prima pagina."))
        else:
            days = (flyer.valid_to - flyer.valid_from).days + 1
            if days > 31:
                out.append(Finding("warn", "date_lunghe", f"Il volantino dura {days} giorni: è voluto?",
                                   "Controlla le date in prima pagina."))
            if flyer.valid_to < today:
                out.append(Finding("info", "date_passate", f"Il volantino è finito il {flyer.valid_to:%d/%m/%Y}.",
                                   "Se è la bozza di un volantino nuovo, le date sono da aggiornare."))
        if doc is not None:
            text_pages = sum(1 for p in doc if p.get_text("text").strip())
        # ------------------------------------------------ storico del negozio (per i refusi e l'Omnibus)
        history = [o for f in session.scalars(select(Flyer).where(Flyer.store_id == store.id, Flyer.competitor == "",
                                                                  Flyer.status == FlyerStatus.ready,
                                                                  Flyer.id != flyer.id))
                   for o in f.offers]
        from .omnibus import _price_in_format, _same_product, check as omnibus_check
        omni = {x.offer.id: x for x in omnibus_check(session, store, flyer)}
        unseen: list[str] = []                 # prezzi al kg da controllare a occhio (volantino fatto di immagini)
        # ------------------------------------------------ offerta per offerta
        for i, o in enumerate(offers):
            lab = _label(o)

            def add(sev, code, msg, fix=""):
                out.append(Finding(sev, code, msg, fix, o.id, lab, o.page))

            if o.price_cents <= 0:
                add("err", "prezzo_zero", "Prezzo a zero o mancante.", "Scrivi il prezzo.")
                continue
            if o.price_cents > 50000:
                add("warn", "prezzo_alto", f"Prezzo molto alto: {format_eur(o.price_cents)}.", "Controlla le cifre.")
            if not o.price_verified:
                add("warn", "lettura_incerta", f"Il prezzo {format_eur(o.price_cents)} è stato letto con incertezza.",
                    "Guardalo sulla bozza.")
            if o.old_price_cents is not None and o.old_price_cents <= o.price_cents:
                add("err", "barrato_basso", f"Il prezzo barrato ({format_eur(o.old_price_cents)}) non è più alto del "
                    f"prezzo in offerta ({format_eur(o.price_cents)}).", "Correggi uno dei due prezzi.")
            if o.id in omni:
                x = omni[o.id]
                add("err", "omnibus", f"Prezzo barrato {format_eur(o.old_price_cents)}, ma nei 30 giorni prima lo "
                    f"stesso prodotto era a {format_eur(x.lowest_cents)} nel volantino del negozio.",
                    f"Come prezzo «prima» va indicato {format_eur(x.lowest_cents)} (regola Omnibus).")
            box = _box_text(doc, o)
            # sconto stampato diverso da quello vero
            if box is not None and o.old_price_cents and o.old_price_cents > o.price_cents:
                real = round((o.old_price_cents - o.price_cents) * 100 / o.old_price_cents)
                printed = {int(p) for p in PCT_RE.findall(box)}
                if printed and real not in printed and all(abs(p - real) >= 2 for p in printed):
                    p = sorted(printed, key=lambda v: abs(v - real))[0]
                    add("err", "sconto_sbagliato", f"Stampato -{p}%, ma da {format_eur(o.old_price_cents)} a "
                        f"{format_eur(o.price_cents)} lo sconto è -{real}%.", f"Scrivi -{real}% (o correggi i prezzi).")
            # prezzo al kg / al litro
            need = _needs_unit_price(o)
            if need is not None:
                cents, label = need
                printed_unit = unit_prices(" ".join([o.unit_price_text or "", box or ""]))
                has_unit_words = bool(UNIT_RE.search((o.unit_price_text or "") + " " + (box or "")))
                expected = format_eur(int(round(cents)))
                if o.unit_price_text or has_unit_words:
                    if printed_unit and all(abs(c - cents) > max(2, cents * 0.02) for c in printed_unit):
                        add("err", "unitario_sbagliato", f"Prezzo {label} stampato {format_eur(printed_unit[0])}, ma con "
                            f"{format_eur(o.price_cents)} per {o.description or 'questo formato'} risulta {expected}.",
                            f"Scrivi {expected} {label}.")
                elif box is not None:
                    add("err", "unitario_mancante", f"Manca il prezzo {label} (dovrebbe essere {expected} {label}).",
                        "Va indicato anche nel volantino quando c'è il prezzo di vendita (Direttiva 98/6/CE).")
                else:
                    unseen.append(f"{lab}: {expected} {label}")
            # formato mancante
            if (o.category or "altro") not in LOOSE and not quantity(o.description or "") and not quantity(o.name) \
                    and not re.search(r"\bal\s*(kg|pezzo|litro)\b", f"{o.description} {o.name}".lower()):
                add("warn", "formato_mancante", "Manca il formato (es. «500 g», «1 litro», «6 x 1,5 L»).",
                    "Senza formato il cliente non può confrontare il prezzo e manca il prezzo al kg.")
            # probabile refuso rispetto ai volantini precedenti
            prev = []
            for h in history:
                if _same_product(o, h):
                    c = _price_in_format(h, o)
                    if c:
                        prev.append(c)
            if prev:
                ref = sorted(prev)[len(prev) // 2]
                ratio = o.price_cents / ref
                if ratio >= 4 or ratio <= 0.25:
                    add("err", "refuso", f"{format_eur(o.price_cents)} è {'molto più alto' if ratio > 1 else 'molto più basso'} "
                        f"del solito: nei volantini precedenti era intorno a {format_eur(ref)}.",
                        "Probabile errore di battitura (una virgola o una cifra): controlla.")
            # lo stesso prodotto due volte
            for p in offers[i + 1:]:
                if p.price_cents != o.price_cents and similarity(o, p) >= 0.9:
                    qa, qb = quantity(o.description or ""), quantity(p.description or "")
                    same_size = (qa is None and qb is None) or (qa and qb and abs(qa.amount - qb.amount) < 1)
                    if same_size:
                        add("warn", "doppione", f"Compare due volte con prezzi diversi: {format_eur(o.price_cents)} "
                            f"(pagina {o.page}) e {format_eur(p.price_cents)} (pagina {p.page}).",
                            "Tieni un solo prezzo, o differenzia il nome (varianti, formati).")
        if unseen:
            out.append(Finding("info", "unitario_da_vedere",
                               f"Il volantino è fatto di immagini: controlla a occhio che ci sia il prezzo al kg/litro "
                               f"su {len(unseen)} prodotti confezionati.",
                               "Valori giusti: " + "; ".join(unseen[:12]) + ("…" if len(unseen) > 12 else "")))
    finally:
        if doc is not None:
            doc.close()
    order = {"err": 0, "warn": 1, "info": 2}
    out.sort(key=lambda f: (order[f.severity], f.page or 0))
    counts = {k: sum(1 for f in out if f.severity == k) for k in order}
    bad_offers = len({f.offer_id for f in out if f.offer_id and f.severity == "err"})
    if counts["err"]:
        verdict = f"{counts['err']} errori da correggere prima della stampa"
    elif counts["warn"]:
        verdict = f"Nessun errore, {counts['warn']} cose da controllare"
    else:
        verdict = "Nessun errore trovato: pronto per la stampa"
    return {"verdict": verdict, "counts": counts, "offers": len(offers), "offers_with_errors": bad_offers,
            "text_pdf": text_pages > 0, "findings": [f.as_dict() for f in out]}


# ----------------------------------------------------------------- rapporto PDF per il grafico

def report_pdf(store: Store, flyer: Flyer, rep: dict, out: Path) -> Path:
    import pymupdf
    from .report import _font
    doc = pymupdf.open()
    W, H = pymupdf.paper_size("a4")
    M = 46
    INK, MUTED = (0.08, 0.11, 0.18), (0.42, 0.45, 0.52)
    colors = {"err": (0.78, 0.16, 0.12), "warn": (0.72, 0.45, 0.0), "info": (0.2, 0.4, 0.7)}
    reg, bold = _font("pr"), _font("pb")
    offers = {o.id: o for o in flyer.offers}
    page = None
    y = 0.0

    def new_page():
        nonlocal page, y
        page = doc.new_page(width=W, height=H)
        page.insert_font(fontname="r", fontbuffer=reg.buffer)
        page.insert_font(fontname="b", fontbuffer=bold.buffer)
        y = M

    def text(x, s, size=10, b=False, color=INK, width=W - 2 * M):
        nonlocal y
        rect = pymupdf.Rect(x, y, x + width, y + 400)
        left = page.insert_textbox(rect, s, fontname="b" if b else "r", fontsize=size, color=color,
                                   lineheight=1.25)
        return 400 - left if left >= 0 else size * 1.3

    new_page()
    y += text(M, "Rapporto di correzione del volantino", 20, True)
    y += 4
    title = flyer.title or "Volantino"
    vt = f" · dal {flyer.valid_from:%d/%m} al {flyer.valid_to:%d/%m}" if flyer.valid_from and flyer.valid_to else ""
    y += text(M, f"{store.name} · {title}{vt}", 11, color=MUTED)
    y += 6
    y += text(M, f"{rep['verdict']}. Offerte controllate: {rep['offers']}.", 12, True,
              colors["err"] if rep["counts"]["err"] else INK)
    y += text(M, "Promovo segnala; i prezzi li decide il negozio e le correzioni le fa il grafico.", 9, color=MUTED)
    y += 10
    for f in rep["findings"]:
        o = offers.get(f["offer_id"])
        thumb = o.crop_path if o is not None and o.crop_path and Path(o.crop_path).exists() else None
        need = 86 if thumb else 52
        if y + need > H - M:
            new_page()
        top = y
        x = M
        if thumb:
            page.insert_image(pymupdf.Rect(M, top, M + 72, top + 72), filename=thumb, keep_proportion=True)
            x = M + 84
        page.draw_rect(pymupdf.Rect(x, top + 2, x + 6, top + 14), color=colors[f["severity"]],
                       fill=colors[f["severity"]])
        y = top
        head = f"{f['severity_label']}" + (f" · pagina {f['page']}" if f.get("page") else "") + \
               (f" · {f['offer']}" if f.get("offer") else "")
        y += text(x + 12, head, 9.5, True, colors[f["severity"]], W - M - x - 12)
        y += text(x + 12, f["message"], 10, False, INK, W - M - x - 12)
        if f.get("fix"):
            y += text(x + 12, "→ " + f["fix"], 9.5, False, MUTED, W - M - x - 12)
        y = max(y, top + (78 if thumb else 0)) + 10
        page.draw_line((M, y - 5), (W - M, y - 5), color=(0.88, 0.87, 0.84), width=0.5)
    if not rep["findings"]:
        y += text(M, "Nessuna segnalazione.", 11)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(out)
    doc.close()
    return out
