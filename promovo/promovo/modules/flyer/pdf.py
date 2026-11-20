"""Lettura del PDF del volantino: pagine, testo con posizioni, immagini, ritagli."""
from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

from ... import pdfdoc
from PIL import Image

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


IMAGE_SIGNATURES = (b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n", b"RIFF")
MAX_IMAGE_PIXELS = 60_000_000


def image_to_pdf(data: bytes) -> bytes:
    """Un volantino in JPG, PNG o WEBP diventa un PDF di una pagina, letto come gli altri."""
    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
    try:
        with Image.open(io.BytesIO(data)) as im:
            im.load()
            if im.width * im.height > MAX_IMAGE_PIXELS:
                raise InvalidPDF("L'immagine è troppo grande.")
            rgb = im.convert("RGB")
    except InvalidPDF:
        raise
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        raise InvalidPDF("L'immagine è danneggiata o in un formato non supportato.") from exc
    buf = io.BytesIO()
    rgb.save(buf, format="PNG")
    doc = pdfdoc.new_document()
    page = doc.new_page(width=rgb.width, height=rgb.height)
    page.insert_image(page.rect, stream=buf.getvalue())
    return doc.tobytes()


def normalize_upload(data: bytes) -> bytes:
    """Accetta PDF e immagini; restituisce sempre un PDF."""
    if not data:
        raise InvalidPDF("Il file è vuoto.")
    if data.startswith(b"%PDF"):
        return data
    if data.startswith(IMAGE_SIGNATURES[:2]) or (data[:4] == b"RIFF" and data[8:12] == b"WEBP"):
        return image_to_pdf(data)
    raise InvalidPDF("Formato non supportato: carica un PDF oppure un'immagine JPG, PNG o WEBP.")


def open_pdf(data: bytes) -> pdfdoc.Document:
    if not data.startswith(b"%PDF"):
        raise InvalidPDF("Il file non è un PDF.")
    try:
        doc = pdfdoc.open(stream=data, filetype="pdf")
    except Exception as exc:  # il lettore PDF solleva vari tipi di errore
        raise InvalidPDF("Il PDF è danneggiato o non leggibile.") from exc
    if doc.needs_pass:
        raise InvalidPDF("Il PDF è protetto da password.")
    if doc.page_count == 0:
        raise InvalidPDF("Il PDF non contiene pagine.")
    if doc.page_count > MAX_PAGES:
        raise InvalidPDF(f"Il PDF ha {doc.page_count} pagine: il massimo è {MAX_PAGES}.")
    return doc


def page_info(page: pdfdoc.Page) -> PageInfo:
    spans: list[Span] = []
    for sp in page.spans():
        txt = sp["text"].strip()
        if txt:
            spans.append(Span(text=txt, bbox=sp["bbox"], size=sp["size"], bold=sp["bold"]))
    area = page.rect.width * page.rect.height
    images = []
    for info in page.get_image_info():
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


def render_page_png(page: pdfdoc.Page, max_side: int = 1568) -> bytes:
    """Immagine della pagina per la lettura con l'IA (lato lungo limitato)."""
    longest = max(page.rect.width, page.rect.height)
    zoom = max_side / longest
    pix = page.get_pixmap(matrix=pdfdoc.Matrix(zoom, zoom), alpha=False)
    return pix.tobytes("png")


def render_half_png(page: pdfdoc.Page, half: int, max_side: int = 1568, overlap: float = 0.06) -> bytes:
    """Metà superiore (0) o inferiore (1) della pagina, con un po' di sovrapposizione, ingrandita."""
    w, h = page.rect.width, page.rect.height
    y0 = 0 if half == 0 else h * (0.5 - overlap)
    y1 = h * (0.5 + overlap) if half == 0 else h
    rect = pdfdoc.Rect(0, y0, w, y1)
    zoom = max_side / max(rect.width, rect.height)
    return page.get_pixmap(matrix=pdfdoc.Matrix(zoom, zoom), clip=rect, alpha=False).tobytes("png")


def render_crop(page: pdfdoc.Page, bbox_norm: list[float], out_path: Path, dpi: int = 220,
                pad: float = 0.01) -> Path:
    """Ritaglio ad alta risoluzione del riquadro normalizzato (0..1) di un prodotto."""
    w, h = page.rect.width, page.rect.height
    x0, y0, x1, y1 = bbox_norm
    rect = pdfdoc.Rect(max(0.0, x0 - pad) * w, max(0.0, y0 - pad) * h,
                        min(1.0, x1 + pad) * w, min(1.0, y1 + pad) * h)
    zoom = dpi / 72
    pix = page.get_pixmap(matrix=pdfdoc.Matrix(zoom, zoom), clip=rect, alpha=False)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pix.save(str(out_path))
    return out_path


def extract_photo(page: pdfdoc.Page, bbox_norm: list[float], out_path: Path, dpi: int = 260) -> Path:
    """Foto del solo prodotto, ad alta risoluzione e scontornata quando lo sfondo è uniforme."""
    from ...imaging import save_product_photo
    w, h = page.rect.width, page.rect.height
    x0, y0, x1, y1 = bbox_norm
    rect = pdfdoc.Rect(x0 * w, y0 * h, x1 * w, y1 * h)
    zoom = dpi / 72
    pix = page.get_pixmap(matrix=pdfdoc.Matrix(zoom, zoom), clip=rect, alpha=False)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    return save_product_photo(img, out_path)


def clean_card(page: pdfdoc.Page, bbox_norm: list[float], erase: list[list[float]], out_path: Path,
               dpi: int = 260) -> Path | None:
    """Il riquadro dell'offerta senza nome, prezzi e sconti stampati (ricostruendo lo sfondo):
    resta il prodotto, pronto per video e grafiche che hanno già il loro cartellino del prezzo."""
    import cv2
    import numpy as np
    from ...imaging import save_product_photo
    w, h = page.rect.width, page.rect.height
    x0, y0, x1, y1 = bbox_norm
    rect = pdfdoc.Rect(x0 * w, y0 * h, x1 * w, y1 * h)
    zoom = dpi / 72
    pix = page.get_pixmap(matrix=pdfdoc.Matrix(zoom, zoom), clip=rect, alpha=False)
    rgb = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)[..., :3].copy()
    mask = np.zeros(rgb.shape[:2], np.uint8)
    gray = rgb.mean(axis=2)
    for ex0, ey0, ex1, ey1 in erase:
        px0 = int((ex0 - x0) / max(1e-9, x1 - x0) * pix.width)
        py0 = int((ey0 - y0) / max(1e-9, y1 - y0) * pix.height)
        px1 = int((ex1 - x0) / max(1e-9, x1 - x0) * pix.width)
        py1 = int((ey1 - y0) / max(1e-9, y1 - y0) * pix.height)
        m = max(3, int(0.18 * (py1 - py0)))
        # Si ricostruisce lo sfondo solo se intorno alla scritta è uniforme: su foto o bollini colorati
        # resterebbero delle macchie, e allora meglio il riquadro originale del volantino.
        r = 2 * m
        ring = gray[max(0, py0 - r):py1 + r, max(0, px0 - r):px1 + r].copy()
        inner = np.zeros_like(ring, bool)
        inner[min(r, py0):min(r, py0) + max(0, py1 - py0), min(r, px0):min(r, px0) + max(0, px1 - px0)] = True
        vals = ring[~inner]
        if vals.size and (np.abs(vals - np.median(vals)) < 18).mean() < 0.8:
            return None
        mask[max(0, py0 - m):max(0, py1 + m), max(0, px0 - m):max(0, px1 + m)] = 255
    if mask.any():
        rgb = cv2.inpaint(rgb, mask, 7, cv2.INPAINT_TELEA)
    # via il vuoto intorno al prodotto: si tiene solo ciò che non è sfondo, con un piccolo margine
    border = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]]).astype(int)
    bg = np.median(border, axis=0)
    fg = np.abs(rgb.astype(int) - bg).sum(axis=2) > 40
    fg = cv2.morphologyEx(fg.astype(np.uint8), cv2.MORPH_OPEN, np.ones((11, 11), np.uint8)) > 0   # via linee e residui sottili
    ys, xs = np.nonzero(fg)
    if len(xs) > 0.01 * fg.size:
        x_0, x_1 = np.percentile(xs, [0.5, 99.5]).astype(int)
        y_0, y_1 = np.percentile(ys, [0.5, 99.5]).astype(int)
        pad = int(0.06 * max(x_1 - x_0, y_1 - y_0))
        rgb = rgb[max(0, y_0 - pad):y_1 + pad, max(0, x_0 - pad):x_1 + pad]
    return save_product_photo(Image.fromarray(rgb), out_path)
