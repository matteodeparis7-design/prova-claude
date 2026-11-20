"""Controlli aggiuntivi per i volantini fatti solo di immagini (nessun testo nel PDF).

Livello 1 - Lettura ottica sul computer: il prezzo viene riletto sul ritaglio ingrandito
            del prodotto; se compare lo stesso prezzo, grande, è confermato.
Livello 2 - Doppia lettura con l'IA facoltativa: i prezzi ancora non confermati vengono riletti
            da Claude. Se le due letture coincidono il prezzo è confermato; se no resta da controllare.
Nessun controllo cambia mai un prezzo da solo: conferma o segnala.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from ... import pdfdoc
from pydantic import BaseModel, Field

from ...llm import AIRefused, AIUnavailable, LLM, image_block
from ...money import format_eur, parse_price
from . import ocr

log = logging.getLogger("promovo.crosscheck")

AI_BATCH = 8


@dataclass
class OcrPrice:
    cents: int
    cx: float   # centro normalizzato 0..1
    cy: float
    h: float


def ocr_available() -> bool:
    return ocr.available()


def ocr_crop_prices(page: pdfdoc.Page, bbox: list[float]) -> list[OcrPrice]:
    """I prezzi stampati nel ritaglio di un'offerta, con posizione e altezza (coordinate della pagina)."""
    w, h = page.rect.width, page.rect.height
    x0, y0, x1, y1 = (max(0.0, bbox[0] - 0.01), max(0.0, bbox[1] - 0.01), min(1.0, bbox[2] + 0.01),
                      min(1.0, bbox[3] + 0.01))
    clip = pdfdoc.Rect(x0 * w, y0 * h, x1 * w, y1 * h)
    if clip.width < 4 or clip.height < 4:
        return []
    rgb = ocr.render(page, max_side=int(min(1600, max(500, 4 * max(clip.width, clip.height)))), clip=clip)
    out = []
    for ln in ocr._lines_from(rgb, x0, y0, x1 - x0, y1 - y0):
        ocr.classify(ln)
        if ln.kind == "price" and ln.cents:
            out.append(OcrPrice(ln.cents, ln.cx, ln.cy, ln.h))
    return out


def _inside(p: OcrPrice, bbox: list[float], pad: float = 0.01) -> bool:
    x0, y0, x1, y1 = bbox
    return x0 - pad <= p.cx <= x1 + pad and y0 - pad <= p.cy <= y1 + pad


def confirm_by_ocr(page: pdfdoc.Page, o) -> bool:
    """Il prezzo dell'offerta compare, grande, nel suo ritaglio? (i prezzi piccoli sono al kg o barrati)"""
    found = [p for p in ocr_crop_prices(page, o.bbox) if _inside(p, o.bbox)]
    if not found:
        return False
    tallest = max(p.h for p in found)
    big = {p.cents for p in found if p.h >= 0.6 * tallest}
    return o.price_cents in big and len(big) <= 2


class AICheckItem(BaseModel):
    index: int = Field(description="Numero dell'immagine, come indicato")
    price: str | None = Field(description="Prezzo finale in offerta stampato, es. '1,99'; null se illeggibile")


class AICheck(BaseModel):
    items: list[AICheckItem]


_CHECK_SYSTEM = (
    "Sei l'agente Controllo di Promovo. Ricevi ritagli numerati di un volantino, ognuno con un prodotto. "
    "Per ciascun ritaglio scrivi il prezzo finale in offerta stampato più in evidenza, esattamente come "
    "stampato (es. '1,99'). Non usare il prezzo al kg o al litro né il prezzo barrato. Se non è leggibile "
    "con certezza, rispondi null. Non indovinare."
)


def _crop_png(page: pdfdoc.Page, bbox: list[float], max_side: int = 700) -> bytes:
    w, h = page.rect.width, page.rect.height
    x0, y0, x1, y1 = bbox
    rect = pdfdoc.Rect(max(0, x0 - 0.01) * w, max(0, y0 - 0.01) * h, min(1, x1 + 0.01) * w, min(1, y1 + 0.01) * h)
    longest = max(rect.width, rect.height) or 1
    zoom = max(1.0, min(6.0, max_side / longest))
    return page.get_pixmap(matrix=pdfdoc.Matrix(zoom, zoom), clip=rect, alpha=False).tobytes("png")


def crosscheck(offers: list, doc: pdfdoc.Document, llm: LLM | None, pages_without_text: set[int],
               already_read: bool = False) -> list[str]:
    """Conferma i prezzi delle pagine senza testo. Modifica le offerte; restituisce gli avvisi.
    already_read: le offerte vengono dalla lettura ottica, che ha già fatto la sua doppia lettura."""
    warnings: list[str] = []
    todo = [o for o in offers if o.page in pages_without_text and not o.price_verified]
    if not todo:
        return warnings

    if not already_read and ocr_available():
        for o in todo:
            try:
                if confirm_by_ocr(doc[o.page - 1], o):
                    o.price_verified = True
                    o.verified_by = "OCR"
            except ocr.OcrUnavailable:
                break

    todo = [o for o in todo if not o.price_verified]
    if todo and llm is not None:
        disagreements = 0
        try:
            for start in range(0, len(todo), AI_BATCH):
                batch = todo[start:start + AI_BATCH]
                content: list[dict] = []
                for i, o in enumerate(batch, start=1):
                    content.append({"type": "text", "text": f"Immagine {i}:"})
                    content.append(image_block(_crop_png(doc[o.page - 1], o.bbox)))
                content.append({"type": "text", "text": f"Rispondi per le immagini da 1 a {len(batch)}."})
                res = llm.parse(system=_CHECK_SYSTEM, content=content, schema=AICheck, effort="low",
                                max_tokens=4000)
                readings = {it.index: parse_price(it.price) if it.price else None for it in res.items}
                for i, o in enumerate(batch, start=1):
                    second = readings.get(i)
                    if second is not None and second == o.price_cents:
                        o.price_verified = True
                        o.verified_by = "doppia lettura IA"
                    elif second is not None:
                        disagreements += 1
                        warnings.append(f"Pagina {o.page}, «{o.name}»: letto {format_eur(o.price_cents)} "
                                        f"e poi {format_eur(second)}. Controllare.")
        except (AIUnavailable, AIRefused) as exc:
            warnings.append(f"Doppia lettura IA non completata: {exc}")
        if disagreements:
            log.info("%d prezzi con letture diverse", disagreements)

    left = sum(1 for o in offers if o.page in pages_without_text and not o.price_verified)
    if left:
        warnings.append(f"{left} prezzi non confermati dalla seconda lettura: da controllare a mano.")
    return warnings
