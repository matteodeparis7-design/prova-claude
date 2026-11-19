"""Scontorno dei prodotti con BiRefNet lite (licenza MIT), sul computer, senza internet.

Dalla foto di un'offerta ritagliata dal volantino restituisce il prodotto su fondo trasparente.
Il risultato si usa solo se è sensato (un oggetto ben definito, né minuscolo né grande quanto tutta la foto):
altrimenti Promovo tiene il metodo di prima. Non inventa nulla: toglie solo lo sfondo.
"""
from __future__ import annotations

import logging
import re
import threading

import numpy as np
from PIL import Image, ImageFilter

from . import extras

log = logging.getLogger("promovo.cutout")

SIZE = 1024
_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
_session = None
_lock = threading.Lock()


def available() -> bool:
    import os
    if os.environ.get("PROMOVO_CUTOUT", "on").lower() in ("off", "0", "no"):
        return False
    return extras.path("cutout") is not None


def _get_session():
    global _session
    if _session is None:
        folder = extras.path("cutout")
        if folder is None:
            return None
        import onnxruntime as ort
        opts = ort.SessionOptions()
        opts.log_severity_level = 3          # niente avvisi tecnici nella finestra
        _session = ort.InferenceSession(str(folder / extras.EXTRAS["cutout"].files[0].name), opts,
                                        providers=["CPUExecutionProvider"])
    return _session


def mask(img: Image.Image) -> np.ndarray | None:
    """Maschera del soggetto principale (0..1, stessa misura della foto), oppure None se il modello manca."""
    sess = _get_session()
    if sess is None:
        return None
    rgb = img.convert("RGB")
    x = np.asarray(rgb.resize((SIZE, SIZE), Image.BILINEAR), dtype=np.float32) / 255.0
    x = ((x - _MEAN) / _STD).transpose(2, 0, 1)[None].astype(np.float32)
    with _lock:                              # una foto alla volta: il modello usa già tutti i processori
        out = sess.run(None, {sess.get_inputs()[0].name: x})[0]
    m = 1 / (1 + np.exp(-out[0, 0].astype(np.float32)))
    return np.asarray(Image.fromarray((m * 255).astype(np.uint8)).resize(rgb.size, Image.BILINEAR),
                      dtype=np.float32) / 255.0


_PRICE = re.compile(r"\d+\s*[,.]\s*\d{1,2}|€|^\s*\d{1,3}\s*$")


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-zà-ù]{4,}", (text or "").lower())}


def carries_offer_text(cutout_img: Image.Image, offer_text: str = "") -> bool:
    """Lettura ottica sul prodotto scontornato: se ci sono rimasti il prezzo o le scritte dell'offerta
    (pezzi del cartellino attaccati al prodotto) lo scontorno non va bene. Le scritte della confezione
    (marchi, «olio extravergine»...) invece restano: sono parte del prodotto."""
    try:
        from .modules.flyer import ocr
        if not ocr.available():
            return False
        flat = Image.new("RGB", cutout_img.size, (255, 255, 255))
        flat.paste(cutout_img, (0, 0), cutout_img)
        lines = ocr.run_ocr(np.asarray(flat))
    except Exception:
        return False
    name = _words(offer_text)
    for _box, text, score in lines:
        if score < 0.6:
            continue
        if _PRICE.search(text):
            return True
        # due o più parole del nome dell'offerta scritte come nel cartellino del volantino
        if name and len(_words(text) & name) >= 2:
            return True
    return False


def cut(img: Image.Image, offer_text: str = "") -> Image.Image | None:
    """Il prodotto su fondo trasparente, ritagliato stretto. None se lo scontorno non è affidabile."""
    m = mask(img)
    if m is None:
        return None
    solid = m > 0.5
    # si tengono solo le parti grandi del soggetto: via i pezzetti di scritte staccati dal prodotto
    import cv2
    n, labels, stats, _ = cv2.connectedComponentsWithStats(solid.astype(np.uint8), connectivity=8)
    if n > 2:
        areas = stats[1:, cv2.CC_STAT_AREA].astype(float)
        H, Wd = solid.shape

        def intruder(i: int) -> bool:
            """Pezzo di un prodotto vicino entrato nel ritaglio: tagliato dal bordo per buona parte del suo lato."""
            x, y, w, h = stats[i + 1, :4]
            cut = 0.0
            if x <= 1:
                cut = max(cut, np.count_nonzero(labels[y:y + h, 0] == i + 1) / max(h, 1))
            if x + w >= Wd - 1:
                cut = max(cut, np.count_nonzero(labels[y:y + h, Wd - 1] == i + 1) / max(h, 1))
            if y <= 1:
                cut = max(cut, np.count_nonzero(labels[0, x:x + w] == i + 1) / max(w, 1))
            if y + h >= H - 1:
                cut = max(cut, np.count_nonzero(labels[H - 1, x:x + w] == i + 1) / max(w, 1))
            return cut > 0.25
        big = [i for i in range(n - 1) if areas[i] >= 0.12 * areas.max()]
        inside = [i for i in big if not intruder(i)]
        main = max(inside, key=lambda i: areas[i]) if inside and max(areas[i] for i in inside) >= 0.3 * areas.max() \
            else int(np.argmax(areas))
        keep = [main + 1] + [i + 1 for i in inside if i != main and areas[i] >= 0.2 * areas[main]]
        solid = np.isin(labels, keep)
        m = np.where(cv2.dilate(solid.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0, m, 0)
    share = float(solid.mean())
    if share < 0.03 or share > 0.92:          # niente soggetto chiaro, oppure è tutta la foto
        return None
    # quanto è netta la maschera: tanti valori a metà = il modello non è sicuro
    unsure = float(((m > 0.2) & (m < 0.8)).mean()) / max(share, 1e-6)
    if unsure > 0.35:
        return None
    ys, xs = np.where(solid)
    pad = max(4, int(0.02 * max(img.size)))
    box = (max(0, xs.min() - pad), max(0, ys.min() - pad), min(img.width, xs.max() + pad + 1),
           min(img.height, ys.max() + pad + 1))
    alpha = Image.fromarray((np.clip(m, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6))
    rgba = img.convert("RGB").copy()
    rgba.putalpha(alpha)
    out = rgba.crop(box)
    if carries_offer_text(out, offer_text):
        return None
    return out
