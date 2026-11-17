"""Lettura del PDF del volantino: pagine, testo con posizioni, immagini, ritagli."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pymupdf

MAX_PAGES = 60


class InvalidPDF(ValueError):
    pass


@dataclass
class Span:
    text: str
    bbox: tuple[float, float, float, float]   # in punti PDF
    size: float
    bold: bool


@dataclass
class PageInfo:
    number: int                     # 1-based
    width: float
    height: float
    text: str
    spans: list[Span]
    images: list[tuple[float, float, float, float]]


def open_pdf(data: bytes) -> pymupdf.Document:
    if not data.startswith(b"%PDF"):
        raise InvalidPDF("Il file non è un PDF.")
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:  # pymupdf solleva vari tipi di errore
        raise InvalidPDF("Il PDF è danneggiato o non leggibile.") from exc
    if doc.needs_pass:
        raise InvalidPDF("Il PDF è protetto da password.")
    if doc.page_count == 0:
        raise InvalidPDF("Il PDF non contiene pagine.")
    if doc.page_count > MAX_PAGES:
        raise InvalidPDF(f"Il PDF ha {doc.page_count} pagine: il massimo è {MAX_PAGES}.")
    return doc


def page_info(page: pymupdf.Page) -> PageInfo:
    spans: list[Span] = []
    data = page.get_text("dict")
    for block in data.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for sp in line.get("spans", []):
                txt = sp.get("text", "").strip()
                if not txt:
                    continue
                spans.append(Span(
                    text=txt,
                    bbox=tuple(sp["bbox"]),
                    size=float(sp.get("size", 0)),
                    bold=bool(sp.get("flags", 0) & 16) or "bold" in sp.get("font", "").lower(),
                ))
    area = page.rect.width * page.rect.height
    images = []
    for info in page.get_image_info(xrefs=True):
        x0, y0, x1, y1 = info["bbox"]
        x0, y0 = max(x0, 0), max(y0, 0)
        x1, y1 = min(x1, page.rect.width), min(y1, page.rect.height)
        a = max(0.0, x1 - x0) * max(0.0, y1 - y0)
        # Esclude icone minuscole e sfondi a tutta pagina.
        if 0.004 * area <= a <= 0.55 * area:
            images.append((x0, y0, x1, y1))
    return PageInfo(
        number=page.number + 1,
        width=page.rect.width,
        height=page.rect.height,
        text=page.get_text("text"),
        spans=spans,
        images=images,
    )


def render_page_png(page: pymupdf.Page, max_side: int = 1568) -> bytes:
    """Immagine della pagina per la lettura con l'IA (lato lungo limitato)."""
    longest = max(page.rect.width, page.rect.height)
    zoom = max_side / longest
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
    return pix.tobytes("png")


def render_crop(page: pymupdf.Page, bbox_norm: list[float], out_path: Path, dpi: int = 220,
                pad: float = 0.01) -> Path:
    """Ritaglio ad alta risoluzione del riquadro normalizzato (0..1) di un prodotto."""
    w, h = page.rect.width, page.rect.height
    x0, y0, x1, y1 = bbox_norm
    rect = pymupdf.Rect(max(0.0, x0 - pad) * w, max(0.0, y0 - pad) * h,
                        min(1.0, x1 + pad) * w, min(1.0, y1 + pad) * h)
    zoom = dpi / 72
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=rect, alpha=False)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pix.save(str(out_path))
    return out_path
