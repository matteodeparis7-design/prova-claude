"""Elaborazione delle immagini: scontorno dei prodotti, logo del negozio."""
from __future__ import annotations

import io
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


class ImageError(ValueError):
    pass


def _border_color(rgb: np.ndarray) -> np.ndarray:
    edge = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]])
    return np.median(edge, axis=0)


def remove_background(img: Image.Image, threshold: int = 34) -> Image.Image | None:
    """Scontorna un prodotto su sfondo uniforme (bianco o colorato).

    Lo sfondo è la zona collegata ai bordi con un colore simile a quello dei bordi.
    Restituisce None se lo sfondo non è uniforme (foto ambientata): meglio la foto intera
    che uno scontorno sbagliato.
    """
    rgb = img.convert("RGB")
    arr = np.asarray(rgb).astype(np.int16)
    h, w = arr.shape[:2]
    if h < 8 or w < 8:
        return None
    edge = np.concatenate([arr[0], arr[-1], arr[:, 0], arr[:, -1]])
    bg = np.median(edge, axis=0)
    # Bordi non uniformi: niente scontorno.
    if np.mean(np.abs(edge - bg).sum(axis=1) < threshold * 1.5) < 0.6:
        return None
    # Riempimento a partire da una cornice di 1 px del colore di sfondo.
    pad = Image.new("RGB", (w + 2, h + 2), tuple(int(c) for c in bg))
    pad.paste(rgb, (1, 1))
    sentinel = (255, 0, 255) if tuple(int(c) for c in bg) != (255, 0, 255) else (0, 255, 0)
    ImageDraw.floodfill(pad, (0, 0), sentinel, thresh=threshold)
    filled = np.all(np.asarray(pad)[1:-1, 1:-1] == sentinel, axis=2)
    frac_bg = filled.mean()
    if frac_bg < 0.04 or frac_bg > 0.93:
        return None
    mask = Image.fromarray(np.where(filled, 0, 255).astype(np.uint8))
    # Bordo morbido e piccoli buchi chiusi.
    mask = mask.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.8))
    out = rgb.convert("RGBA")
    out.putalpha(mask)
    box = mask.point(lambda v: 255 if v > 24 else 0).getbbox()
    if box is None:
        return None
    return out.crop(box)


def open_image(data: bytes, max_pixels: int = 40_000_000) -> Image.Image:
    """Apre un'immagine caricata da un utente, con controlli su formato e dimensioni."""
    if not data:
        raise ImageError("Il file è vuoto.")
    try:
        with Image.open(io.BytesIO(data)) as im:
            im.load()
            if im.width * im.height > max_pixels:
                raise ImageError("L'immagine è troppo grande.")
            return im.convert("RGBA") if im.mode in ("RGBA", "LA", "P") else im.convert("RGB")
    except ImageError:
        raise
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        raise ImageError("Il file non è un'immagine valida (usa JPG, PNG o WEBP).") from exc


def save_product_photo(img: Image.Image, out_path: Path, max_side: int = 1400) -> Path:
    """Salva la foto del prodotto, scontornata quando possibile (PNG con trasparenza)."""
    if img.mode == "RGBA" and img.getchannel("A").getextrema()[0] < 255:
        # Già scontornata (PNG con trasparenza): si taglia solo il margine vuoto.
        box = img.getchannel("A").point(lambda v: 255 if v > 10 else 0).getbbox()
        final = img.crop(box) if box else img
    else:
        cut = remove_background(img)
        final = cut if cut is not None else img.convert("RGBA")
    final.thumbnail((max_side, max_side), Image.LANCZOS)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    final.save(out_path, format="PNG", optimize=True)
    return out_path


def load_logo(data: bytes, out_path: Path, max_side: int = 800) -> Path:
    """Valida e salva il logo del negozio (PNG, JPG o WEBP) come PNG con trasparenza."""
    if not data:
        raise ImageError("Il file è vuoto.")
    if len(data) > 8 * 1024 * 1024:
        raise ImageError("Il logo supera 8 MB.")
    try:
        with Image.open(io.BytesIO(data)) as im:
            im.load()
            if im.width * im.height > 40_000_000:
                raise ImageError("Il logo è troppo grande.")
            logo = im.convert("RGBA")
    except ImageError:
        raise
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        raise ImageError("Il logo non è un'immagine valida (usa PNG, JPG o WEBP).") from exc
    # Un logo su sfondo pieno (tipico dei JPG) viene scontornato; uno già trasparente resta com'è.
    alpha = np.asarray(logo.getchannel("A"))
    if alpha.min() == 255:
        cut = remove_background(logo, threshold=28)
        if cut is not None:
            logo = cut
    box = logo.getchannel("A").point(lambda v: 255 if v > 10 else 0).getbbox()
    if box:
        logo = logo.crop(box)
    logo.thumbnail((max_side, max_side), Image.LANCZOS)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    logo.save(out_path, format="PNG", optimize=True)
    return out_path
