"""Controlli aggiuntivi per i volantini fatti solo di immagini (nessun testo nel PDF).

Livello 1 - OCR (Tesseract, se installato): legge i prezzi stampati nella pagina e
            conferma quelli che compaiono dentro il riquadro dell'offerta.
Livello 2 - Doppia lettura IA: i prezzi non confermati vengono riletti da Claude su un
            ritaglio ingrandito del singolo prodotto. Se le due letture coincidono il prezzo
            è confermato; se sono diverse viene segnalato e resta "da controllare".
Nessun controllo cambia mai un prezzo da solo: conferma o segnala.
"""
from __future__ import annotations

import csv
import io
import logging
import shutil
import subprocess
from dataclasses import dataclass

import numpy as np
import pymupdf
from PIL import Image, ImageFilter
from pydantic import BaseModel, Field

from ...llm import AIRefused, AIUnavailable, LLM, image_block
from ...money import find_prices, format_eur, parse_price

log = logging.getLogger("promovo.crosscheck")

OCR_DPI = 150
# Altezza minima (in frazione della pagina) del testo di un prezzo principale: esclude
# i prezzi al kg/litro stampati in piccolo, che non devono confermare il prezzo dell'offerta.
MIN_PRICE_HEIGHT = 0.012
AI_BATCH = 8


@dataclass
class OcrPrice:
    cents: int
    cx: float   # centro normalizzato 0..1
    cy: float


def ocr_available() -> bool:
    return shutil.which("tesseract") is not None


def _tesseract_tsv(img: Image.Image, digits_only: bool) -> list[dict]:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    cmd = ["tesseract", "stdin", "stdout", "--psm", "11"]
    if digits_only:
        cmd += ["-c", "tessedit_char_whitelist=0123456789,."]
    else:
        cmd += ["-l", "ita"]
    cmd.append("tsv")
    try:
        out = subprocess.run(cmd, input=buf.getvalue(), capture_output=True, timeout=120, check=True).stdout
    except (subprocess.SubprocessError, OSError) as exc:
        log.warning("OCR non riuscito: %s", exc)
        return []
    rows = list(csv.DictReader(io.StringIO(out.decode("utf-8", errors="replace")), delimiter="\t",
                               quoting=csv.QUOTE_NONE))
    return [r for r in rows if (r.get("text") or "").strip()]


def _variants(rgb: np.ndarray) -> list[tuple[Image.Image, bool]]:
    """Versioni dell'immagine che aiutano l'OCR: originale e testo colorato isolato."""
    r, g, b = (rgb[..., i].astype(int) for i in range(3))
    out = [(Image.fromarray(rgb).convert("L"), False)]
    masks = [
        (r > 140) & (g < 120) & (b < 120) & (r - g > 60),    # prezzi rossi (i più comuni)
        (r + g + b < 200),                                    # prezzi neri o molto scuri
        (r > 200) & (g > 200) & (b > 200),                    # prezzi bianchi su riquadri colorati
    ]
    for m in masks:
        img = Image.fromarray(np.where(m, 0, 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3))
        out.append((img, True))
    return out


def ocr_page_prices(page: pymupdf.Page) -> list[OcrPrice]:
    pix = page.get_pixmap(dpi=OCR_DPI, alpha=False)
    rgb = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)[..., :3]
    found: list[OcrPrice] = []
    for img, digits in _variants(rgb):
        for row in _tesseract_tsv(img, digits):
            prices = find_prices(row["text"])
            if len(prices) != 1:
                continue
            try:
                left, top, w, h = (float(row[k]) for k in ("left", "top", "width", "height"))
            except (KeyError, ValueError):
                continue
            if h / pix.height < MIN_PRICE_HEIGHT:
                continue
            found.append(OcrPrice(prices[0], (left + w / 2) / pix.width, (top + h / 2) / pix.height))
    return found


def _inside(p: OcrPrice, bbox: list[float], pad: float = 0.01) -> bool:
    x0, y0, x1, y1 = bbox
    return x0 - pad <= p.cx <= x1 + pad and y0 - pad <= p.cy <= y1 + pad


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


def _crop_png(page: pymupdf.Page, bbox: list[float], max_side: int = 700) -> bytes:
    w, h = page.rect.width, page.rect.height
    x0, y0, x1, y1 = bbox
    rect = pymupdf.Rect(max(0, x0 - 0.01) * w, max(0, y0 - 0.01) * h, min(1, x1 + 0.01) * w, min(1, y1 + 0.01) * h)
    longest = max(rect.width, rect.height) or 1
    zoom = max(1.0, min(6.0, max_side / longest))
    return page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=rect, alpha=False).tobytes("png")


def crosscheck(offers: list, doc: pymupdf.Document, llm: LLM | None, pages_without_text: set[int]) -> list[str]:
    """Conferma i prezzi delle pagine senza testo. Modifica le offerte; restituisce gli avvisi."""
    warnings: list[str] = []
    todo = [o for o in offers if o.page in pages_without_text and not o.price_verified]
    if not todo:
        return warnings

    if ocr_available():
        by_page: dict[int, list[OcrPrice]] = {}
        for o in todo:
            if o.page not in by_page:
                by_page[o.page] = ocr_page_prices(doc[o.page - 1])
            if any(p.cents == o.price_cents and _inside(p, o.bbox) for p in by_page[o.page]):
                o.price_verified = True
                o.verified_by = "OCR"
    else:
        warnings.append("OCR non installato: controllo dei prezzi solo con la doppia lettura dell'IA.")

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
        warnings.append(f"{left} prezzi di pagine senza testo non confermati: da controllare a mano.")
    return warnings
