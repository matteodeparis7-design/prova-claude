"""Agente "Lettore": estrae le offerte da un volantino.

Due metodi:
1. IA (Claude vede ogni pagina e legge anche il testo del PDF): il più preciso.
2. Euristico (solo testo e immagini del PDF, senza IA): di riserva.

Dopo l'estrazione ogni prezzo viene verificato contro il testo reale del PDF
(agente "Controllo"): un prezzo che non compare nel PDF viene segnalato.
"""
from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from datetime import date

import pymupdf
from pydantic import BaseModel, Field

from ...llm import AIRefused, AIUnavailable, LLM, image_block
from ...money import discount_percent, find_prices, parse_price
from ...text_utils import CATEGORIES, coerce_category, normalize, parse_iso_date, parse_validity
from .crosscheck import crosscheck
from .pdf import PageInfo, Span, page_info, render_page_png

log = logging.getLogger("promovo.flyer")

MAX_PRICE_CENTS = 1_000_000  # 10.000 €: oltre è certamente un errore di lettura


@dataclass
class RawOffer:
    page: int
    name: str
    price_cents: int
    bbox: list[float]
    brand: str = ""
    description: str = ""
    category: str = "altro"
    old_price_cents: int | None = None
    discount_percent: int | None = None
    unit_price_text: str = ""
    conditions: str = ""
    price_verified: bool = False
    verified_by: str = ""
    photo_bbox: list[float] | None = None     # solo la foto del prodotto, se individuata


@dataclass
class ExtractionResult:
    offers: list[RawOffer]
    method: str
    title: str = ""
    valid_from: date | None = None
    valid_to: date | None = None
    warnings: list[str] = field(default_factory=list)


# ------------------------------------------------------------------ schema per l'IA

class AIOffer(BaseModel):
    name: str = Field(description="Nome del prodotto come scritto, senza marca se la marca è separata")
    brand: str = Field(description="Marca, stringa vuota se assente")
    description: str = Field(description="Formato, peso, varianti, es. '500 g', 'assortiti'")
    category: str = Field(description="Una tra: " + ", ".join(CATEGORIES))
    price: str = Field(description="Prezzo finale in offerta esattamente come stampato, es. '1,99'")
    old_price: str | None = Field(description="Prezzo barrato o di listino se stampato, altrimenti null")
    discount_percent: int | None = Field(description="Sconto percentuale se stampato, altrimenti null")
    unit_price_text: str = Field(description="Prezzo al kg o al litro se stampato, es. '€ 3,98 al kg'")
    conditions: str = Field(description="Condizioni, es. 'con carta fedeltà', 'prendi 3 paghi 2'")
    x0: int = Field(description="Bordo sinistro del riquadro del prodotto, 0-1000")
    y0: int = Field(description="Bordo superiore, 0-1000")
    x1: int = Field(description="Bordo destro, 0-1000")
    y1: int = Field(description="Bordo inferiore, 0-1000")
    photo_x0: int = Field(description="Riquadro della SOLA foto del prodotto, senza prezzi né scritte: bordo sinistro 0-1000")
    photo_y0: int = Field(description="Foto del prodotto: bordo superiore 0-1000")
    photo_x1: int = Field(description="Foto del prodotto: bordo destro 0-1000")
    photo_y1: int = Field(description="Foto del prodotto: bordo inferiore 0-1000")


class AIPage(BaseModel):
    offers: list[AIOffer]


class AIMeta(BaseModel):
    title: str = Field(description="Titolo o tema del volantino, stringa vuota se assente")
    store_or_banner: str = Field(description="Insegna o negozio, stringa vuota se assente")
    valid_from: str | None = Field(description="Data di inizio validità in formato AAAA-MM-GG, o null")
    valid_to: str | None = Field(description="Data di fine validità in formato AAAA-MM-GG, o null")


_PAGE_SYSTEM = (
    "Sei l'agente Lettore di Promovo. Ricevi una pagina di un volantino promozionale di un "
    "supermercato italiano (immagine e testo estratto dal PDF). Elenca TUTTE le offerte di prodotti "
    "presenti nella pagina, una per prodotto, senza inventare nulla.\n"
    "Regole:\n"
    "- Copia i prezzi esattamente come stampati (es. '1,99'). Se un prezzo non è leggibile, salta il prodotto.\n"
    "- old_price solo se un prezzo barrato o 'invece di' è stampato; altrimenti null.\n"
    "- Il riquadro (x0, y0, x1, y1) è in millesimi della pagina, da 0 a 1000, e deve contenere foto, "
    "nome e prezzo del prodotto.\n"
    "- Il riquadro photo_* contiene SOLO la foto della confezione o del prodotto, il più stretto possibile, "
    "senza prezzi, bollini e scritte; serve per i video e le grafiche.\n"
    "- Ignora loghi, testate, numeri di pagina e scritte decorative.\n"
    "- Se la pagina non contiene offerte, restituisci un elenco vuoto."
)

_META_SYSTEM = (
    "Sei l'agente Lettore di Promovo. Dal testo e dall'immagine della prima pagina di un volantino "
    "ricava il titolo, l'insegna e il periodo di validità. Non inventare: se un dato non c'è, usa "
    "stringa vuota o null. Per l'anno, se manca, usa quello indicato in 'Oggi'."
)


def _clamp_bbox(x0: float, y0: float, x1: float, y1: float) -> list[float] | None:
    x0, x1 = sorted((min(max(x0, 0.0), 1.0), min(max(x1, 0.0), 1.0)))
    y0, y1 = sorted((min(max(y0, 0.0), 1.0), min(max(y1, 0.0), 1.0)))
    if x1 - x0 < 0.01 or y1 - y0 < 0.01:
        return None
    return [round(x0, 4), round(y0, 4), round(x1, 4), round(y1, 4)]


def _ai_offer_to_raw(page_no: int, o: AIOffer) -> RawOffer | None:
    price = parse_price(o.price)
    if price is None or price <= 0 or price > MAX_PRICE_CENTS:
        return None
    name = " ".join(o.name.split())
    if not name:
        return None
    bbox = _clamp_bbox(o.x0 / 1000, o.y0 / 1000, o.x1 / 1000, o.y1 / 1000)
    if bbox is None:
        return None
    photo = _clamp_bbox(o.photo_x0 / 1000, o.photo_y0 / 1000, o.photo_x1 / 1000, o.photo_y1 / 1000)
    # La foto deve stare (quasi) dentro il riquadro dell'offerta e non coincidere con tutto il riquadro.
    if photo is not None:
        inside = (photo[0] >= bbox[0] - 0.02 and photo[1] >= bbox[1] - 0.02 and
                  photo[2] <= bbox[2] + 0.02 and photo[3] <= bbox[3] + 0.02)
        area = (photo[2] - photo[0]) * (photo[3] - photo[1])
        if not inside or area < 0.0004:
            photo = None
    old = parse_price(o.old_price) if o.old_price else None
    if old is not None and old <= price:
        old = None
    disc = o.discount_percent if (o.discount_percent and 0 < o.discount_percent < 100) else None
    return RawOffer(
        page=page_no, name=name[:300], brand=o.brand.strip()[:120], description=o.description.strip()[:500],
        category=coerce_category(o.category, name, o.description), price_cents=price,
        old_price_cents=old, discount_percent=disc or discount_percent(price, old),
        unit_price_text=o.unit_price_text.strip()[:80], conditions=o.conditions.strip()[:300], bbox=bbox,
        photo_bbox=photo,
    )


def extract_with_ai(doc: pymupdf.Document, llm: LLM, today: date | None = None) -> ExtractionResult:
    today = today or date.today()
    offers: list[RawOffer] = []
    warnings: list[str] = []
    for page in doc:
        info = page_info(page)
        png = render_page_png(page)
        content = [
            image_block(png),
            {"type": "text", "text": f"Pagina {info.number} di {doc.page_count}.\n"
                                     f"Testo estratto dal PDF:\n{info.text[:12000] or '(nessun testo)'}"},
        ]
        result = llm.parse(system=_PAGE_SYSTEM, content=content, schema=AIPage, effort="high")
        dropped = 0
        for o in result.offers:
            raw = _ai_offer_to_raw(info.number, o)
            if raw is None:
                dropped += 1
            else:
                offers.append(raw)
        if dropped:
            warnings.append(f"Pagina {info.number}: {dropped} offerte scartate perché incomplete.")

    first = doc[0]
    meta = llm.parse(
        system=_META_SYSTEM,
        content=[image_block(render_page_png(first, 1024)),
                 {"type": "text", "text": f"Oggi: {today.isoformat()}\nTesto:\n{first.get_text('text')[:6000]}"}],
        schema=AIMeta, effort="low", max_tokens=2000)
    vf, vt = parse_iso_date(meta.valid_from), parse_iso_date(meta.valid_to)
    if vf and vt and vf > vt:
        vf, vt = None, None
        warnings.append("Date di validità incoerenti: ignorate.")
    return ExtractionResult(offers=offers, method="ai", title=meta.title.strip()[:300],
                            valid_from=vf, valid_to=vt, warnings=warnings)


# ------------------------------------------------------------------ metodo euristico

def _center(b: tuple[float, float, float, float]) -> tuple[float, float]:
    return (b[0] + b[2]) / 2, (b[1] + b[3]) / 2


def _union(*boxes: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


def _is_noise(text: str) -> bool:
    t = text.strip()
    if len(t) < 3:
        return True
    low = t.lower()
    if find_prices(t) or "%" in t or low.startswith(("€", "eur")):
        return True
    noise = ("offert", "valid", "pagina", "volantino", "fino a esaurimento", "invece di", "sconto",
             "prezzo", "risparmi")
    return any(w in low for w in noise)


def _price_spans(info: PageInfo) -> list[tuple[Span, int]]:
    out = []
    for sp in info.spans:
        prices = find_prices(sp.text)
        if len(prices) == 1 and 0 < prices[0] <= MAX_PRICE_CENTS:
            low = sp.text.lower()
            if "al kg" in low or "al lt" in low or "al litro" in low:
                continue
            out.append((sp, prices[0]))
    return out


def _heuristic_page(info: PageInfo) -> list[RawOffer]:
    prices = _price_spans(info)
    if not prices:
        return []
    # Il prezzo principale è il più grande per corpo del testo; gli altri vicini sono prezzi barrati.
    max_size = max(sp.size for sp, _ in prices)
    main = [(sp, c) for sp, c in prices if sp.size >= 0.6 * max_size]
    secondary = [(sp, c) for sp, c in prices if sp.size < 0.6 * max_size]

    anchors = info.images or []
    used_prices: set[int] = set()
    groups: list[tuple[tuple, Span, int]] = []
    if anchors:
        pairs = []
        for ai, img in enumerate(anchors):
            ic = _center(img)
            for pi, (sp, _) in enumerate(main):
                pc = _center(sp.bbox)
                pairs.append((math.dist(ic, pc), ai, pi))
        used_anchor: set[int] = set()
        diag = math.hypot(info.width, info.height)
        for d, ai, pi in sorted(pairs):
            if ai in used_anchor or pi in used_prices or d > 0.35 * diag:
                continue
            used_anchor.add(ai)
            used_prices.add(pi)
            groups.append((anchors[ai], main[pi][0], main[pi][1]))
    # Prezzi senza immagine: offerta basata sul solo testo.
    for pi, (sp, cents) in enumerate(main):
        if pi not in used_prices:
            groups.append((sp.bbox, sp, cents))

    offers = []
    image_set = set(anchors)
    for anchor, psp, cents in groups:
        region = _union(anchor, psp.bbox)
        rx0, ry0, rx1, ry1 = region
        pad_x, pad_y = 0.08 * info.width, 0.06 * info.height
        # Nome: le righe di testo più vicine al gruppo, privilegiando il corpo più grande.
        cands = []
        for sp in info.spans:
            if _is_noise(sp.text):
                continue
            cx, cy = _center(sp.bbox)
            if rx0 - pad_x <= cx <= rx1 + pad_x and ry0 - pad_y <= cy <= ry1 + pad_y:
                dist = math.dist((cx, cy), _center(region))
                cands.append((-(sp.size), dist, sp))
        cands.sort(key=lambda t: (t[0], t[1]))
        if not cands:
            continue
        name_spans = [cands[0][2]]
        # Seconda riga (es. formato) se vicina e più piccola.
        for _, _, sp in cands[1:3]:
            if abs(sp.bbox[1] - name_spans[0].bbox[3]) < 2.5 * sp.size and sp.size <= name_spans[0].size:
                name_spans.append(sp)
                break
        name = name_spans[0].text.strip()
        description = name_spans[1].text.strip() if len(name_spans) > 1 else ""

        # Prezzo barrato: il più vicino al prezzo principale, entro poche volte la sua altezza
        # (nei volantini fitti un prezzo più lontano appartiene quasi sempre al prodotto accanto).
        old, best = None, None
        reach = 3.5 * max(psp.bbox[3] - psp.bbox[1], psp.size)
        for sp, c in secondary:
            d = math.dist(_center(sp.bbox), _center(psp.bbox))
            if c > cents and d <= reach and (best is None or d < best):
                old, best = c, d
        bb = _union(region, *[s.bbox for s in name_spans])
        bbox = _clamp_bbox(bb[0] / info.width, bb[1] / info.height, bb[2] / info.width, bb[3] / info.height)
        if bbox is None:
            continue
        offers.append(RawOffer(
            page=info.number, name=name[:300], description=description[:500],
            category=coerce_category(None, name, description), price_cents=cents,
            old_price_cents=old, discount_percent=discount_percent(cents, old), bbox=bbox,
            photo_bbox=_clamp_bbox(anchor[0] / info.width, anchor[1] / info.height,
                                   anchor[2] / info.width, anchor[3] / info.height) if anchor in image_set else None,
        ))
    return offers


def extract_heuristic(doc: pymupdf.Document, today: date | None = None) -> ExtractionResult:
    offers: list[RawOffer] = []
    warnings: list[str] = []
    texts = []
    for page in doc:
        info = page_info(page)
        texts.append(info.text)
        if not info.spans:
            warnings.append(f"Pagina {info.number}: nessun testo nel PDF (pagina solo immagine), "
                            "serve l'IA per leggerla.")
            continue
        offers.extend(_heuristic_page(info))
    vf, vt = parse_validity(" ".join(texts[:2]), today)
    title = ""
    first = page_info(doc[0])
    titled = [s for s in first.spans if not _is_noise(s.text)]
    if titled:
        title = max(titled, key=lambda s: s.size).text.strip()[:300]
    return ExtractionResult(offers=offers, method="heuristic", title=title, valid_from=vf, valid_to=vt,
                            warnings=warnings)


# ------------------------------------------------------------------ verifica e pulizia

def verify_and_clean(result: ExtractionResult, doc: pymupdf.Document, llm: LLM | None = None) -> ExtractionResult:
    """Agente Controllo: verifica ogni prezzo contro il testo del PDF e rimuove i doppioni."""
    page_prices: dict[int, set[int]] = {}
    page_percents: dict[int, set[int]] = {}
    has_text: dict[int, bool] = {}
    for page in doc:
        txt = page.get_text("text")
        page_prices[page.number + 1] = set(find_prices(txt))
        page_percents[page.number + 1] = {int(m) for m in re.findall(r"(\d{1,2})\s*%", txt)}
        has_text[page.number + 1] = bool(txt.strip())

    seen: set[tuple] = set()
    cleaned: list[RawOffer] = []
    unverified = 0
    for o in result.offers:
        key = (o.page, normalize(o.name), o.price_cents)
        if key in seen:
            continue
        seen.add(key)
        if has_text.get(o.page):
            o.price_verified = o.price_cents in page_prices.get(o.page, set())
            o.verified_by = "testo PDF" if o.price_verified else ""
            if o.old_price_cents and o.old_price_cents not in page_prices.get(o.page, set()):
                o.old_price_cents = None
            # Lo sconto resta solo se ricavabile dal prezzo barrato o se è stampato nella pagina.
            computed = discount_percent(o.price_cents, o.old_price_cents)
            if computed is not None:
                o.discount_percent = computed
            elif o.discount_percent and o.discount_percent not in page_percents.get(o.page, set()):
                o.discount_percent = None
            if not o.price_verified:
                unverified += 1
        else:
            o.price_verified = False
        cleaned.append(o)
    cleaned.sort(key=lambda o: (o.page, round(o.bbox[1], 2), o.bbox[0]))
    warnings = list(result.warnings)
    if unverified:
        warnings.append(f"{unverified} prezzi non trovati nel testo del PDF: da controllare a mano.")
    no_text = {p for p, t in has_text.items() if not t}
    warnings.extend(crosscheck(cleaned, doc, llm, no_text))
    if not cleaned:
        warnings.append("Nessuna offerta trovata nel volantino.")
    return ExtractionResult(offers=cleaned, method=result.method, title=result.title,
                            valid_from=result.valid_from, valid_to=result.valid_to, warnings=warnings)


def pick_featured(offers: list[RawOffer], limit: int = 6) -> set[int]:
    """Indici delle offerte di punta: sconto più alto, poi prezzo più basso."""
    ranked = sorted(range(len(offers)),
                    key=lambda i: (-(offers[i].discount_percent or 0), offers[i].price_cents))
    return set(ranked[:limit])


def extract_offers(doc: pymupdf.Document, llm: LLM | None, today: date | None = None) -> ExtractionResult:
    """Prova con l'IA; se non è disponibile usa il metodo euristico."""
    if llm is not None:
        try:
            return verify_and_clean(extract_with_ai(doc, llm, today), doc, llm)
        except (AIUnavailable, AIRefused) as exc:
            log.warning("Estrazione con IA non disponibile (%s): uso il metodo euristico.", exc)
            res = verify_and_clean(extract_heuristic(doc, today), doc)
            res.warnings.insert(0, f"IA non disponibile ({exc}): offerte lette con il metodo euristico.")
            return res
    return verify_and_clean(extract_heuristic(doc, today), doc)
