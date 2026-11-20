"""PDF: lettura e scrittura con librerie a licenza permissiva (si possono vendere senza obblighi di codice aperto).

- lettura delle pagine come immagine: pypdfium2 (Apache-2.0 / BSD-3, il motore PDF di Chrome);
- testo, posizioni delle parole e immagini: pdfplumber e pdfminer.six (MIT);
- scrittura dei PDF (report, rapporti, volantini di prova): reportlab (BSD).

Prima Promovo usava PyMuPDF, che ha licenza AGPL: venduto senza pubblicare tutto il codice avrebbe violato la
licenza. Questo modulo offre le poche funzioni che servono con nomi simili (Document, Page, Rect, Matrix), così il
resto del programma resta semplice.
"""
from __future__ import annotations

import io
import threading
from pathlib import Path

from PIL import Image

_LOCK = threading.RLock()          # pdfium non è sicuro con più thread insieme: una pagina alla volta


class PdfError(RuntimeError):
    pass


# ----------------------------------------------------------------- geometria

class Rect:
    """Rettangolo in punti, con l'origine in alto a sinistra (come lo si vede sulla pagina)."""

    def __init__(self, x0: float = 0.0, y0: float = 0.0, x1: float = 0.0, y1: float = 0.0):
        self.x0, self.y0, self.x1, self.y1 = float(x0), float(y0), float(x1), float(y1)

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    def __iter__(self):
        return iter((self.x0, self.y0, self.x1, self.y1))

    def __repr__(self) -> str:
        return f"Rect({self.x0:.1f}, {self.y0:.1f}, {self.x1:.1f}, {self.y1:.1f})"


class Matrix:
    """Solo l'ingrandimento (zoom orizzontale e verticale)."""

    def __init__(self, sx: float, sy: float | None = None):
        self.sx = float(sx)
        self.sy = float(sy if sy is not None else sx)


PAPER = {"a4": (595.0, 842.0), "a3": (842.0, 1191.0)}


def paper_size(name: str) -> tuple[float, float]:
    return PAPER[name.lower()]


def paper_rect(name: str) -> Rect:
    return Rect(0, 0, *paper_size(name))


# ----------------------------------------------------------------- lettura

class Pixmap:
    """Immagine di una pagina (o di una sua parte)."""

    def __init__(self, img: Image.Image):
        self.img = img.convert("RGB")
        self.width, self.height = self.img.size
        self.n = 3

    @property
    def samples(self) -> bytes:
        return self.img.tobytes()

    def tobytes(self, fmt: str = "png") -> bytes:
        buf = io.BytesIO()
        self.img.save(buf, format="PNG" if fmt.lower() == "png" else fmt.upper())
        return buf.getvalue()

    def save(self, path, jpg_quality: int | None = None) -> None:
        if jpg_quality is not None:
            self.img.save(str(path), quality=jpg_quality)
        else:
            self.img.save(str(path))


class Page:
    def __init__(self, doc: "Document", index: int):
        self.parent = doc
        self.number = index
        with _LOCK:
            w, h = doc._pdfium[index].get_size()
        self.rect = Rect(0, 0, w, h)
        self._plumber = None

    # -- testo
    def _pl(self):
        if self._plumber is None:
            self._plumber = self.parent._plumber_doc().pages[self.number]
        return self._plumber

    def _offset(self) -> tuple[float, float]:
        b = self._pl().bbox
        return float(b[0]), float(b[1])

    def get_text(self, kind: str = "text", clip: Rect | None = None) -> str:
        if kind != "text":
            raise ValueError("Solo get_text('text'): per le parole con la posizione usa spans().")
        pl = self._pl()
        if clip is not None:
            ox, oy = self._offset()
            x0, y0 = max(0.0, clip.x0), max(0.0, clip.y0)
            x1, y1 = min(self.rect.width, clip.x1), min(self.rect.height, clip.y1)
            if x1 <= x0 or y1 <= y0:
                return ""
            pl = pl.crop((x0 + ox, y0 + oy, x1 + ox, y1 + oy), strict=False)
        return pl.extract_text() or ""

    def spans(self) -> list[dict]:
        """Pezzi di testo sulla stessa riga con lo stesso carattere: testo, bbox, dimensione, nome del carattere."""
        ox, oy = self._offset()
        words = self._pl().extract_words(extra_attrs=["fontname", "size"], keep_blank_chars=False,
                                         use_text_flow=True, x_tolerance=1.5, y_tolerance=2)
        out: list[dict] = []
        for w in words:
            bbox = [w["x0"] - ox, w["top"] - oy, w["x1"] - ox, w["bottom"] - oy]
            size, fname = float(w["size"]), str(w["fontname"])
            prev = out[-1] if out else None
            if (prev is not None and prev["font"] == fname and abs(prev["size"] - size) < 0.2
                    and abs(prev["bbox"][1] - bbox[1]) < 0.35 * size
                    and 0 <= bbox[0] - prev["bbox"][2] < 0.6 * size):
                prev["text"] += " " + w["text"]
                prev["bbox"][2] = max(prev["bbox"][2], bbox[2])
                prev["bbox"][1] = min(prev["bbox"][1], bbox[1])
                prev["bbox"][3] = max(prev["bbox"][3], bbox[3])
                continue
            out.append({"text": w["text"], "bbox": bbox, "size": size, "font": fname})
        for s in out:
            s["bbox"] = tuple(s["bbox"])
            f = s["font"].lower()
            s["bold"] = any(k in f for k in ("bold", "black", "heavy", "-bd", "semibold"))
        return out

    def get_image_info(self) -> list[dict]:
        ox, oy = self._offset()
        return [{"bbox": (float(i["x0"]) - ox, float(i["top"]) - oy, float(i["x1"]) - ox, float(i["bottom"]) - oy)}
                for i in self._pl().images]

    # -- immagine
    def get_pixmap(self, matrix: Matrix | None = None, clip: Rect | None = None, alpha: bool = False,
                   dpi: int | None = None) -> Pixmap:
        scale = matrix.sx if matrix is not None else (dpi / 72 if dpi else 1.0)
        W, H = self.rect.width, self.rect.height
        crop = (0.0, 0.0, 0.0, 0.0)
        if clip is not None:
            x0, y0 = max(0.0, clip.x0), max(0.0, clip.y0)
            x1, y1 = min(W, clip.x1), min(H, clip.y1)
            if x1 - x0 < 1 or y1 - y0 < 1:
                raise PdfError("Ritaglio fuori dalla pagina.")
            crop = (x0, H - y1, W - x1, y0)        # pdfium: quanto togliere da sinistra, sotto, destra, sopra
        with _LOCK:
            bitmap = self.parent._pdfium[self.number].render(scale=scale, crop=crop)
            img = bitmap.to_pil()
        return Pixmap(img)


class Document:
    def __init__(self, data: bytes):
        import pypdfium2 as pdfium
        self._data = data
        self.needs_pass = False
        self._plumber = None
        self._pages: dict[int, Page] = {}
        with _LOCK:
            try:
                self._pdfium = pdfium.PdfDocument(data)
            except pdfium.PdfiumError as exc:
                if "password" in str(exc).lower():
                    self.needs_pass = True
                    self._pdfium = None
                else:
                    raise PdfError("Il PDF è danneggiato o non leggibile.") from exc

    def _plumber_doc(self):
        if self._plumber is None:
            import pdfplumber
            self._plumber = pdfplumber.open(io.BytesIO(self._data))
        return self._plumber

    @property
    def page_count(self) -> int:
        return 0 if self._pdfium is None else len(self._pdfium)

    def __len__(self) -> int:
        return self.page_count

    def __getitem__(self, i: int) -> Page:
        n = self.page_count
        if i < 0:
            i += n
        if not 0 <= i < n:
            raise IndexError("pagina inesistente")
        if i not in self._pages:
            self._pages[i] = Page(self, i)
        return self._pages[i]

    def __iter__(self):
        for i in range(self.page_count):
            yield self[i]

    def close(self) -> None:
        if self._plumber is not None:
            self._plumber.close()
            self._plumber = None
        if self._pdfium is not None:
            with _LOCK:
                self._pdfium.close()
            self._pdfium = None
        self._pages.clear()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def open(path=None, stream: bytes | None = None, filetype: str | None = None) -> Document:  # noqa: A001
    """Apre un PDF da file o da byte; senza argomenti crea un PDF nuovo da scrivere."""
    if path is None and stream is None:
        return Writer()  # type: ignore[return-value]
    if stream is None:
        stream = Path(path).read_bytes()
    return Document(stream)


# ----------------------------------------------------------------- scrittura

BASE14 = {"helv": "Helvetica", "hebo": "Helvetica-Bold", "heit": "Helvetica-Oblique", "tiro": "Times-Roman",
          "cour": "Courier"}
_registered: dict[str, str] = {}


def _register(fontfile: str) -> str:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    key = str(Path(fontfile).resolve())
    if key not in _registered:
        name = "pv_" + Path(fontfile).stem.replace(" ", "_")
        with _LOCK:
            pdfmetrics.registerFont(TTFont(name, key))
        _registered[key] = name
    return _registered[key]


class Font:
    def __init__(self, fontfile: str | None = None, fontname: str = "helv"):
        self.name = _register(fontfile) if fontfile else BASE14.get(fontname, fontname)

    def text_length(self, text: str, fontsize: float = 11) -> float:
        from reportlab.pdfbase import pdfmetrics
        return pdfmetrics.stringWidth(text, self.name, fontsize)


def get_text_length(text: str, fontname: str = "helv", fontsize: float = 11) -> float:
    return Font(fontname=fontname).text_length(text, fontsize)


class WriterPage:
    def __init__(self, writer: "Writer", width: float, height: float):
        self.w = writer
        self.rect = Rect(0, 0, width, height)
        self.fonts: dict[str, str] = dict(BASE14)

    @property
    def _c(self):
        return self.w._canvas

    def _y(self, y: float) -> float:
        return self.rect.height - y

    def insert_font(self, fontname: str, fontfile: str | None = None) -> None:
        if fontfile:
            self.fonts[fontname] = _register(fontfile)

    def _font(self, name: str) -> str:
        return self.fonts.get(name, self.w.fonts.get(name, BASE14.get(name, "Helvetica")))

    def draw_rect(self, rect: Rect, color=None, fill=None, width: float = 1.0) -> None:
        c = self._c
        if fill is not None:
            c.setFillColorRGB(*fill)
        if color is not None:
            c.setStrokeColorRGB(*color)
            c.setLineWidth(width)
        c.rect(rect.x0, self._y(rect.y1), rect.width, rect.height, stroke=1 if color is not None else 0,
               fill=1 if fill is not None else 0)

    def draw_line(self, p1, p2, color=(0, 0, 0), width: float = 1.0) -> None:
        c = self._c
        c.setStrokeColorRGB(*color)
        c.setLineWidth(width)
        c.line(p1[0], self._y(p1[1]), p2[0], self._y(p2[1]))

    def insert_text(self, point, text: str, fontname: str = "helv", fontsize: float = 11, color=(0, 0, 0)) -> None:
        """Scrive una riga: `point` è l'inizio della linea di base, misurato dall'alto."""
        c = self._c
        c.setFillColorRGB(*color)
        c.setFont(self._font(fontname), fontsize)
        c.drawString(point[0], self._y(point[1]), text)

    def insert_textbox(self, rect: Rect, text: str, fontname: str = "helv", fontsize: float = 11, color=(0, 0, 0),
                       lineheight: float = 1.2) -> float:
        """Testo a capo automatico dentro il riquadro; restituisce lo spazio rimasto (negativo se non ci sta)."""
        from reportlab.pdfbase import pdfmetrics
        fn = self._font(fontname)
        lines: list[str] = []
        for para in text.split("\n"):
            cur = ""
            for word in para.split(" "):
                t = (cur + " " + word).strip()
                if pdfmetrics.stringWidth(t, fn, fontsize) <= rect.width or not cur:
                    cur = t
                else:
                    lines.append(cur)
                    cur = word
            lines.append(cur)
        lh = fontsize * lineheight
        used = len(lines) * lh
        if used > rect.height:
            return rect.height - used
        for i, ln in enumerate(lines):
            self.insert_text((rect.x0, rect.y0 + fontsize + i * lh), ln, fontname, fontsize, color)
        return rect.height - used

    def insert_image(self, rect: Rect, filename=None, stream: bytes | None = None, keep_proportion: bool = True) -> None:
        from reportlab.lib.utils import ImageReader
        src = Image.open(filename) if filename else Image.open(io.BytesIO(stream))
        with src:
            img = src.convert("RGBA") if src.mode in ("RGBA", "LA", "P") else src.convert("RGB")
        iw, ih = img.size
        x, y, w, h = rect.x0, rect.y0, rect.width, rect.height
        if keep_proportion and iw and ih:
            k = min(w / iw, h / ih)
            nw, nh = iw * k, ih * k
            x, y, w, h = x + (w - nw) / 2, y + (h - nh) / 2, nw, nh
        self._c.drawImage(ImageReader(img), x, self._y(y + h), w, h, mask="auto")


class Writer:
    """Un PDF nuovo, pagina dopo pagina (si disegna sempre sull'ultima pagina creata)."""

    def __init__(self):
        from reportlab.pdfgen import canvas
        self._buf = io.BytesIO()
        self._canvas = canvas.Canvas(self._buf, pageCompression=1)
        self._canvas.setTitle("Promovo")
        self._canvas.setAuthor("Promovo")
        self._canvas.setCreator("Promovo")
        self._pages: list[WriterPage] = []
        self.fonts: dict[str, str] = {}
        self._data: bytes | None = None

    def new_page(self, width: float = 595.0, height: float = 842.0) -> WriterPage:
        if self._pages:
            self._canvas.showPage()
        self._canvas.setPageSize((width, height))
        p = WriterPage(self, width, height)
        self._pages.append(p)
        return p

    @property
    def page_count(self) -> int:
        return len(self._pages)

    def tobytes(self, **_kw) -> bytes:
        if self._data is None:
            if not self._pages:
                self.new_page()
            self._canvas.showPage()
            self._canvas.save()
            self._data = self._buf.getvalue()
        return self._data

    def save(self, path, **_kw) -> None:
        Path(path).write_bytes(self.tobytes())

    def close(self) -> None:
        pass


def new_document() -> Writer:
    return Writer()
