"""Agente "Lettore" senza IA esterna: legge i volantini fatti di immagini con il riconoscimento
del testo (OCR) che gira sul computer, e ricostruisce le offerte come farebbe una persona.

1. Legge la pagina: ogni riga di testo con posizione, altezza e affidabilità (RapidOCR, modelli
   multilingua PP-OCR inclusi nel programma: nessun collegamento a internet).
2. Trova i prezzi grandi (quelli delle offerte), separandoli dai prezzi al kg e da quelli barrati.
3. Per ogni prezzo cerca il nome del prodotto: le righe subito sopra (anche su due o tre righe),
   o accanto, con il formato ("500 g") e l'unità ("al kg").
4. Rilegge ogni prezzo una seconda volta su un ritaglio ingrandito: se le due letture coincidono
   il prezzo è confermato, altrimenti resta "da controllare". Un prezzo non viene mai cambiato da solo.
5. Ritaglia la foto del prodotto: la zona colorata accanto al nome, senza scritte.
"""
from __future__ import annotations

import logging
import math
import re
import threading
from dataclasses import dataclass, field

import numpy as np
from ... import pdfdoc
from PIL import Image

from ...money import discount_percent, parse_price
from ...text_utils import coerce_category, normalize

log = logging.getLogger("promovo.ocr")

PAGE_MAX_SIDE = 2400       # risoluzione della lettura: abbastanza per i nomi piccoli, veloce sul PC
MIN_SCORE = 0.5
_engine = None
_engine_lock = threading.Lock()
_engine_error: str | None = None


def available() -> bool:
    import importlib.util
    return all(importlib.util.find_spec(m) is not None for m in ("rapidocr", "onnxruntime"))


def engine():
    """Il motore OCR, creato una volta sola (carica i modelli dal disco)."""
    global _engine, _engine_error
    with _engine_lock:
        if _engine is None and _engine_error is None:
            try:
                from rapidocr import RapidOCR
                _engine = RapidOCR(params={"Global.log_level": "warning", "Global.max_side_len": PAGE_MAX_SIDE,
                                           "Global.text_score": MIN_SCORE})
            except Exception as exc:  # noqa: BLE001
                _engine_error = str(exc)
                log.warning("OCR non disponibile: %s", exc)
        if _engine is None:
            raise OcrUnavailable(_engine_error or "OCR non disponibile")
        return _engine


class OcrUnavailable(RuntimeError):
    pass


# ------------------------------------------------------------------ righe di testo

@dataclass
class Line:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    score: float
    kind: str = ""                   # price | unit | name | format | noise
    cents: int | None = None
    used: bool = False
    busy: float = 0.0                # quanto è "mossa" l'immagine intorno: 0 fondo pulito, 1 foto o disegno

    @property
    def h(self) -> float:
        return self.y1 - self.y0

    @property
    def w(self) -> float:
        return self.x1 - self.x0

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2


def render(page: pdfdoc.Page, max_side: int = PAGE_MAX_SIDE, clip: pdfdoc.Rect | None = None) -> np.ndarray:
    rect = clip or page.rect
    zoom = max_side / max(rect.width, rect.height)
    pix = page.get_pixmap(matrix=pdfdoc.Matrix(zoom, zoom), clip=rect, alpha=False)
    return np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)[..., :3].copy()


def run_ocr(rgb: np.ndarray) -> list[tuple[list, str, float]]:
    res = engine()(rgb[..., ::-1])            # il motore lavora in BGR, come OpenCV
    if res is None or res.boxes is None or res.txts is None:
        return []
    return [(box.tolist() if hasattr(box, "tolist") else box, str(t), float(s))
            for box, t, s in zip(res.boxes, res.txts, res.scores)]


def _lines_from(rgb: np.ndarray, ox: float = 0.0, oy: float = 0.0, sx: float = 1.0, sy: float = 1.0) -> list[Line]:
    """Righe lette in un'immagine; (ox, oy, sx, sy) riportano le coordinate a quelle della pagina."""
    h, w = rgb.shape[:2]
    out = []
    for box, text, score in run_ocr(rgb):
        xs, ys = [p[0] for p in box], [p[1] for p in box]
        text = " ".join(text.split())
        if not text or score < MIN_SCORE:
            continue
        out.append(Line(text, ox + min(xs) / w * sx, oy + min(ys) / h * sy, ox + max(xs) / w * sx,
                        oy + max(ys) / h * sy, score))
    return out


def _iou(a: Line, b: Line) -> float:
    ix = max(0.0, min(a.x1, b.x1) - max(a.x0, b.x0))
    iy = max(0.0, min(a.y1, b.y1) - max(a.y0, b.y0))
    inter = ix * iy
    union = a.w * a.h + b.w * b.h - inter
    return inter / union if union > 0 else 0.0


def _same_text_inside(a: Line, b: Line) -> bool:
    """Due letture della stessa scritta: una contiene l'altra (testo e riquadro)."""
    ix = max(0.0, min(a.x1, b.x1) - max(a.x0, b.x0))
    iy = max(0.0, min(a.y1, b.y1) - max(a.y0, b.y0))
    small = min(a.w * a.h, b.w * b.h)
    if small <= 0 or ix * iy < 0.6 * small:
        return False
    ta, tb = normalize(a.text).replace(" ", ""), normalize(b.text).replace(" ", "")
    return bool(ta and tb) and (ta in tb or tb in ta)


def merge_lines(first: list[Line], second: list[Line]) -> list[Line]:
    """Unisce due letture: dove si sovrappongono tiene la più affidabile, il resto si somma."""
    out = list(first)
    for ln in second:
        twins = [o for o in out if _iou(o, ln) > 0.35 or _same_text_inside(o, ln)]
        if not twins:
            out.append(ln)
            continue
        best = max(twins, key=lambda o: o.score)
        longer = len(normalize(ln.text)) > len(normalize(best.text)) + 2 and _same_text_inside(best, ln)
        if len(twins) == 1 and (ln.score > best.score + 0.05 or (longer and ln.score >= best.score - 0.05)):
            out[out.index(best)] = ln
    return out


def read_lines(page: pdfdoc.Page) -> tuple[list[Line], np.ndarray]:
    """Le righe di testo della pagina (lette a due risoluzioni), con coordinate normalizzate 0..1."""
    rgb = render(page)
    lines = _lines_from(rgb)
    small = render(page, max_side=int(PAGE_MAX_SIDE * 0.75))
    lines = merge_lines(lines, _lines_from(small))
    return lines, rgb


# ------------------------------------------------------------------ cosa dice ogni riga

# L'OCR legge spesso il simbolo € come "e", "c" o "€" attaccato al numero.
_EURO_FIX = re.compile(r"^(?:€|e|c|E|C)\s?(?=\d)")
_PRICE_ONLY = re.compile(r"^(?:€\s?)?(\d{1,4})\s?[,.]\s?(\d{2})(?:\s?€)?$")
_UNIT_WORDS = re.compile(r"\b(al|il|a)\s?(kg|chilo|kilo|lt|litro|l|pezzo|pz|etto|hg)\b", re.I)
_FORMAT = re.compile(r"(?<![\w,.])(\d+(?:[,.]\d+)?\s?(?:x\s?\d+(?:[,.]\d+)?\s?)?(?:kg|g|gr|ml|cl|lt|litri|litro|l|pz|pezzi|rotoli|"
                     r"capsule|lavaggi|bustine|filtri|cialde)\b\.?(?:\s?(?:/|-)\s?\d+(?:[,.]\d+)?\s?(?:g|kg))?)", re.I)
_SIZE_RANGE = re.compile(r"\b\d{2,4}\s?/\s?\d{2,4}\b")       # pezzature del pesce: "300/700"
NOISE = ("volantino", "pagina", "offerte valide", "valide dal", "salvo esaurimento", "fino ad esaurimento", "foto ",
         "immagini", "puramente indicativ", "non sono soggetti", "seguici", "www.", ".it", "@", "pag.",
         "tel.", "orari", "aperto", "domenica", "convenienza")


def clean(text: str) -> str:
    t = text.strip().lstrip(".,'`´-_·:;").strip()
    t = _EURO_FIX.sub("€ ", t)
    return t.replace("€€", "€")


def classify(line: Line) -> None:
    t = clean(line.text)
    line.text = t
    low = t.lower()
    m = _PRICE_ONLY.match(t.replace(" ", "")) or _PRICE_ONLY.match(t)
    if m:
        line.kind, line.cents = "price", int(m.group(1)) * 100 + int(m.group(2))
        return
    if any(n in low for n in NOISE) and not _PRICE_ONLY.match(t):
        line.kind = "noise"
        return
    if _UNIT_WORDS.search(low) and re.search(r"\d", t):
        line.kind = "unit"                                  # "al kg 7,98"
        return
    if _UNIT_WORDS.fullmatch(low.strip()) or low.strip() in ("al pezzo", "alpezzo", "al kg", "alkg", "cad.", "cad"):
        line.kind = "unit"
        return
    letters = sum(c.isalpha() for c in t)
    if len(t) > 60 or any(n in low for n in NOISE):
        line.kind = "noise"
        return
    if _FORMAT.fullmatch(t.strip()) or (letters <= 4 and _FORMAT.search(t)):
        line.kind = "format"
        return
    if letters >= 3 and letters >= 0.5 * len(t.replace(" ", "")):
        line.kind = "name"
        return
    line.kind = "noise"


# ------------------------------------------------------------------ dalle righe alle offerte

_KEEP_UPPER = {"DOP", "IGP", "DOC", "DOCG", "IGT", "UHT", "BIO", "XL", "XXL", "UE", "BBQ", "TV"}


_FINAL_ACCENT_OK = {"perché", "né", "sé", "poiché", "affinché", "cioè", "tè"}


def fix_accents(word: str) -> str:
    """In italiano l'accento cade solo sull'ultima lettera: "CALÀMARO" -> "CALAMARO", "MELÉ" -> "MELE"."""
    import unicodedata
    plain = "".join(c for c in unicodedata.normalize("NFD", word) if not unicodedata.combining(c))
    if plain == word or len(word) < 2:
        return word
    core = word.rstrip(".,;:/")
    tail = word[len(core):]
    body = "".join(c for c in unicodedata.normalize("NFD", core[:-1]) if not unicodedata.combining(c))
    body = unicodedata.normalize("NFC", body)
    last = core[-1]
    if last.lower() in "éÉ" and core.lower() not in _FINAL_ACCENT_OK:
        last = "e" if last.islower() else "E"
    return body + last + tail


# Parole della spesa: servono a separare quelle che l'OCR attacca ("LIMONIDISORRENTO").
VOCAB = set("""
di del della dello dei delle degli da dal dalla al alla allo ai alle a e ed in con per su tra fra il lo la i gli le un una uno
te vicini vicino fresco fresca freschi fresche nostro nostra
acqua aglio agnello albicocche alici amaretti ananas anatra anguria arance arancia aranciata asparagi avocado
baccala banane barbabietole basilico bastoncini bevanda bianco bianca biologico birra biscotti bistecca bosco bresaola
brodo burro cacao caffe caffè calamari calamaro camomilla cappuccina capperi carciofi carne carote castagne cavolfiore
cavolo ceci cereali cetrioli champignon cicoria ciliegie cioccolato cipolle cipollotti coca cola cocomero confettura
coniglio coppa cornetti cotechino cotto cozze crema crudo dec decongelato detersivo dolce dole dop
erbette fagioli fagiolini farina fave fette filetto finocchi fiordilatte fior formaggio fragole frollini frutti funghi
gamberi gambero gelato golden gorgonzola grana granny grattugiato grissini guanciale
igp insalata kiwi lamponi lattuga latte lenticchie limoni limone lupini lupino maccheroni macinato mais mandarini
mandorle mango manzo mammole marmellata mascarpone mela mele melanzane melinda melone merluzzo miele mirtilli
misto mista mortadella mozzarella naturale nazionale nespole noci nocciole olio olive orata origano ossobuco
pancetta pane panna parmigiano passata pasta patate patatine pecorino peperoni pere pesca pesce pesche petto
piselli pistacchi pizza polenta pollo polpa pomodori pomodorini pomodoro porchetta porri porro prezzemolo
prosciutto provola provolone prugne puntarelle radicchio ravanelli red delicious ricotta riso rosa rossa rosso
rucola salame salmone salsiccia sarde scamorza sedano seppie sgombro sorrento spaghetti speck spigola spinaci
stracchino succo susine tacchino taleggio tonno torta trota uova uva verza vino vitello vongole wurstel yogurt
zucca zucchero zucchine affettati affettato pulite pulito pulita lungo lunga tondo tonda cappuccio forno vapore
mammola rossi rosse bianchi bianche verde verdi nero nera neri piccoli grandi
classica classiche classico classici original originale regular zero light uovo sorpresa colomba
pandoro panettone lasagne sfoglia vaschetta confezione tranci trancio fusi cosce sovracosce
spiedini hamburger macinata bocconcini birra peroni
""".split())


def split_glued(word: str) -> str:
    """Separa una parola lunga fatta di parole note ("carciofimammole" -> "carciofi mammole")."""
    w = normalize(word)
    if len(w) < 9 or w in VOCAB or not w.isalpha():
        return word
    best: list[list[str] | None] = [None] * (len(w) + 1)
    best[0] = []
    for i in range(1, len(w) + 1):
        for j in range(max(0, i - 14), i):
            if best[j] is not None and w[j:i] in VOCAB:
                cand = best[j] + [w[j:i]]
                if best[i] is None or len(cand) < len(best[i]):
                    best[i] = cand
    parts = best[len(w)]
    if not parts:
        # una marca che non conosciamo seguita da parole note: "fioruccisalame" -> "fiorucci salame"
        for k in range(4, len(w) - 3):
            tail = w[k:]
            if best[len(w)] is None and tail in VOCAB:
                parts = [w[:k], tail]
                break
    if not parts or len(parts) < 2 or any(len(p) == 1 and p not in ("a", "e") for p in parts):
        return word
    # rimette le lettere originali (maiuscole, accenti) nelle posizioni giuste
    out, k = [], 0
    for p in parts:
        out.append(word[k:k + len(p)])
        k += len(p)
    return " ".join(out)


def nice_name(text: str) -> str:
    """ "GAMBERO ROSA NAZIONALE" -> "Gambero rosa nazionale" (le sigle restano maiuscole)."""
    text = re.sub(r"(?<=[A-Za-zÀ-ÿ])(?=\d)|(?<=\d)(?=[A-Za-zÀ-ÿ]{2})", " ", text)
    text = re.sub(r"\s*/\s*", " / ", text) if re.search(r"[A-Za-z]\s*/\s*[A-Za-z]", text) else text
    words = [split_glued(fix_accents(w)) for w in text.split()]
    words = " ".join(words).split()
    if sum(c.isupper() for c in text) < 0.6 * max(1, sum(c.isalpha() for c in text)):
        return " ".join(words)                              # già scritto con minuscole: si rispetta
    out = []
    for i, w in enumerate(words):
        if w.strip(".,").upper() in _KEEP_UPPER:
            out.append(w.upper())
        else:
            out.append(w.capitalize() if i == 0 else w.lower())
    name = " ".join(out)
    return re.sub(r"\bd'(\w)", lambda m: "d'" + m.group(1), name)


def split_format(name: str) -> tuple[str, str]:
    """ "Asparagi 500g" -> ("Asparagi", "500 g"); "Spigola 300/700" -> ("Spigola", "300/700")."""
    name = name.replace("·", " ")
    name = re.sub(r"(\d\s?[xX]\s?)(\d+[.,]\d{1,2})1\b", r"\1\2 l", name)        # "4x1.501" -> "4x1.50 l"
    name = re.sub(r"\b(g|gr|kg|ml|cl)\s?(\d{2,4})\b", r"\2 \1", name, flags=re.I)  # "g 250" -> "250 g"
    name = re.sub(r"(?<=[A-Za-zÀ-ÿ])(?=\d)", " ", name)
    fmt = []
    for rx in (_FORMAT, _SIZE_RANGE):
        for m in list(rx.finditer(name)):
            fmt.append(m.group(0))
            name = name.replace(m.group(0), " ")
    pretty = [re.sub(r"(\d)\s?(kg|g|gr|ml|cl|lt|l)\b", r"\1 \2", f, flags=re.I).replace("gr", "g") for f in fmt]
    pretty = [re.sub(r"(\d)\s?[xX]\s?(?=\d)", r"\1 x ", f) for f in pretty]
    return " ".join(name.split()).strip(" -·,"), " ".join(pretty)


@dataclass
class OcrOffer:
    page: int
    name: str
    description: str
    price_cents: int
    old_price_cents: int | None
    unit_price_text: str
    bbox: list[float]
    photo_bbox: list[float] | None
    price_line: Line
    lines: list[Line] = field(default_factory=list)


def _x_overlap(a: Line, b: Line) -> float:
    return max(0.0, min(a.x1, b.x1) - max(a.x0, b.x0))


def _stack_down(first: Line, names: list[Line]) -> list[Line]:
    """Nome sotto il prezzo: le righe successive allineate e della stessa altezza continuano il nome."""
    group, last = [first], first
    while len(group) < 4:
        cand = [n for n in names if not n.used and n not in group and n.y0 >= last.y1 - 0.25 * last.h
                and n.y0 - last.y1 < 1.1 * max(last.h, n.h) and _x_overlap(n, last) > 0.25 * min(n.w, last.w)
                and 0.7 * last.h < n.h < 1.35 * last.h]
        if not cand:
            break
        last = min(cand, key=lambda n: n.y0)
        group.append(last)
    return group


def _is_upper(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    return bool(letters) and sum(c.isupper() for c in letters) >= 0.7 * len(letters)


class Cells:
    """Le caselle della pagina (zone chiuse dai bordi): un nome e un prezzo in caselle diverse non
    possono essere della stessa offerta."""

    def __init__(self, rgb: np.ndarray | None = None):
        self.map = None
        if rgb is None:
            return
        import cv2
        H, W = rgb.shape[:2]
        k = 800 / max(H, W)
        small = cv2.resize(rgb, (max(1, int(W * k)), max(1, int(H * k))), interpolation=cv2.INTER_AREA)
        n, lab = cv2.connectedComponents((~_walls(small)).astype(np.uint8), connectivity=4)
        area = np.bincount(lab.ravel(), minlength=n)
        h, w = lab.shape
        small_cells = (area < 0.2 * w * h) & (area > 0.003 * w * h)
        small_cells[0] = False
        self.map = np.where(small_cells[lab], lab, 0)

    def of(self, x: float, y: float) -> int:
        if self.map is None:
            return 0
        h, w = self.map.shape
        return int(self.map[min(h - 1, max(0, int(y * h))), min(w - 1, max(0, int(x * w)))])

    def apart(self, a: Line, b: Line) -> bool:
        ca, cb = self.of(a.cx, a.cy), self.of(b.cx, b.cy)
        return bool(ca and cb and ca != cb)


_CELLS = threading.local()


def _cells() -> Cells:
    return getattr(_CELLS, "value", None) or Cells()


def _name_distance(price: Line, n: Line, below: bool) -> float | None:
    """Quanto un nome è "suo" per questo prezzo (None se non può esserlo)."""
    if _cells().apart(price, n):
        return None
    reach = max(6 * price.h, 0.09)
    if below:
        vertical = n.cy > price.cy and n.y0 - price.y1 <= reach and n.y0 >= price.y0
        dy = max(0.0, n.y0 - price.y1)
    else:
        vertical = n.cy < price.cy and price.y0 - n.y1 <= reach and n.y1 <= price.y1
        dy = max(0.0, price.y0 - n.y1)
    beside = (abs(n.cy - price.cy) < 1.2 * price.h and _x_overlap(n, price) == 0
              and min(abs(n.x0 - price.x1), abs(price.x0 - n.x1)) < 3 * price.h)
    if not (vertical or beside):
        return None
    slack = max(price.w, n.w) * 0.9 + price.h
    if vertical and not (n.x1 > price.x0 - slack and n.x0 < price.x1 + slack):
        return None
    if not vertical:
        dy = 0.0
    dx = abs(n.cx - price.cx) if not _x_overlap(n, price) else 0.0
    return dy + 0.6 * dx + (0.3 * price.h if beside and not vertical else 0) + (0.01 * n.y1 if below else -0.01 * n.y1)


def _pick_name(price: Line, names: list[Line], extra: list[Line] | None = None, below: bool = False) -> list[Line]:
    """Le righe del nome per un prezzo: la più vicina sopra (o sotto, secondo l'impaginazione della
    pagina), più quelle che continuano il nome su altre righe."""
    best, best_d = None, None
    for n in names:
        if n.used:
            continue
        d = _name_distance(price, n, below)
        if d is not None and (best_d is None or d < best_d):
            best, best_d = n, d
    if best is None:
        return []
    if below:
        return _stack_down(best, names)
    group = [best]
    # Righe impilate sopra (il nome su più righe): si sale riga per riga, scavalcando anche
    # formati e prezzi al kg stampati in mezzo, finché il blocco di testo continua.
    pool = [n for n in names if not n.used] + [ln for ln in (extra or []) if ln.kind in ("format", "unit")]
    top = best
    climbed: list[Line] = []
    while len(climbed) < 6:
        cand = [n for n in pool if n is not top and n not in climbed and n not in group
                and n.y1 <= top.y0 + 0.25 * top.h and top.y0 - n.y1 < 1.25 * max(top.h, n.h)
                and _x_overlap(n, top) > 0.25 * min(n.w, top.w) and 0.55 * top.h < n.h < 1.45 * top.h]
        if not cand:
            break
        top = max(cand, key=lambda n: n.y1)
        climbed.append(top)
    group = [n for n in reversed(climbed) if n.kind == "name"] + group
    # una riga subito sotto il nome e sopra il prezzo (es. "AMMOLLATO")
    bottom = group[-1]
    below = [n for n in names if not n.used and n not in group and n.cy > bottom.cy + 0.6 * bottom.h
             and n.y0 - bottom.y1 < 1.1 * bottom.h and n.y1 <= price.y0 + 0.35 * price.h
             and 0.55 * bottom.h < n.h < 1.45 * bottom.h
             and _x_overlap(n, bottom) > 0.3 * min(n.w, bottom.w)]
    if below:
        group.append(min(below, key=lambda n: n.y0))
    group.sort(key=lambda g: (round(g.y0, 3), g.x0))
    # Il nome vero è in MAIUSCOLO; le righe in minuscolo sotto sono varianti ("barbie, hot wheels").
    upper = [g for g in group if _is_upper(g.text)]
    if upper and len(upper) < len(group):
        for g in group:
            if g not in upper:
                g.used = True       # le varianti non devono diventare il nome di un'altra offerta
        group = upper
    return group


def _near(lines: list[Line], kind: str, box: tuple[float, float, float, float], used_ok: bool = False) -> list[Line]:
    x0, y0, x1, y1 = box
    return [ln for ln in lines if ln.kind == kind and (used_ok or not ln.used)
            and x0 <= ln.cx <= x1 and y0 <= ln.cy <= y1]


def lines_to_offers(lines: list[Line], page_no: int) -> list[OcrOffer]:
    for ln in lines:
        classify(ln)
    prices = [ln for ln in lines if ln.kind == "price" and 0 < (ln.cents or 0) <= 1_000_000]
    if not prices:
        return []
    names = [ln for ln in lines if ln.kind == "name"]
    # Titoli di reparto ("ORTOFRUTTA") e slogan: molto più grandi dei nomi dei prodotti.
    if names:
        typical = float(np.median([n.h for n in names]))
        for n in names:
            if n.h > 2.4 * typical:
                n.kind = "noise"
        names = [n for n in names if n.kind == "name"]
    # Prezzi principali: i più grandi; i piccoli vicini a uno grande sono prezzi barrati.
    tall = sorted((p.h for p in prices), reverse=True)
    ref = tall[min(len(tall) - 1, max(0, len(tall) // 5))]
    main = sorted([p for p in prices if p.h >= 0.55 * ref], key=lambda p: (round(p.y0, 2), p.x0))
    small = [p for p in prices if p not in main]
    # Impaginazione della pagina: nome sopra il prezzo o sotto? Si provano tutte e due e si tiene
    # quella che abbina più prodotti con distanze più corte (come farebbe una persona a colpo d'occhio).
    # Le didascalie hanno quasi tutte la stessa altezza: si prova anche usando solo quelle
    # (così le scritte stampate sulle confezioni non vengono prese per il nome del prodotto).
    # Si prova la pagina in più modi e si tiene la lettura più coerente:
    # - con tutte le righe;
    # - senza le scritte minuscole (spesso stampate sulle confezioni): tra le altezze che si ripetono
    #   su molti prodotti si prende la più grande come riferimento e si tolgono quelle sotto la metà;
    # - con le sole righe dell'altezza più frequente (le didascalie hanno tutte lo stesso stile).
    pools = [names]
    if names:
        hs = sorted(n.h for n in names)
        viable = [x for x in hs if sum(1 for y in hs if 0.8 * x <= y <= 1.25 * x) >= max(2, 0.6 * len(main))]
        if viable:
            ref_h = max(viable)
            readable = [n for n in names if n.h >= 0.5 * ref_h]
            if len(readable) < len(names):
                pools.append(readable)
        best_h = max(hs, key=lambda x: sum(1 for y in hs if 0.8 * x <= y <= 1.25 * x))
        same = [n for n in names if 0.8 * best_h <= n.h <= 1.25 * best_h]
        if len(same) < len(names) and len(same) >= 0.7 * len(main):
            pools.append(same)
    results = []
    for k, pool in enumerate(pools):
        for below in (False, True):
            for ln in lines:
                ln.used = False
            pairs = _assign(main, pool, lines, below)
            cost = sum(d for d, _, _ in pairs) / max(1, len(pairs))
            hs_ = [(g[0] if below else g[-1]).h for _, _, g in pairs]
            cv = float(np.std(hs_) / np.mean(hs_)) if len(hs_) > 1 else 0.0
            ph = float(np.median([p.h for _, p, _ in pairs])) if pairs else 1.0
            busy = float(np.mean([g.busy for _, _, grp in pairs for g in grp])) if pairs else 0.0
            results.append((len(pairs), -(cost / ph + 3.0 * cv + 1.5 * busy), below, k))
    _, _, best_below, best_pool = max(results)
    for ln in lines:
        ln.used = False
    return [_make_offer(p, group, lines, small, page_no)
            for _, p, group in _assign(main, pools[best_pool], lines, best_below)]


def _unused_old_mode(main, names, lines, small, page_no):        # pragma: no cover - tenuto per riferimento
    results = []
    for below in (False, True):
        for ln in lines:
            ln.used = False
        pairs = _assign(main, names, lines, below)
        cost = sum(d for d, _, _ in pairs) / max(1, len(pairs))
        # Le didascalie di un volantino hanno tutte lo stesso stile; le scritte sulle confezioni no.
        hs = [(g[0] if below else g[-1]).h for _, _, g in pairs]
        cv = float(np.std(hs) / np.mean(hs)) if len(hs) > 1 else 0.0
        ph = float(np.median([p.h for _, p, _ in pairs])) if pairs else 1.0
        results.append((len(pairs), -(cost / ph + 3.0 * cv), below))
    best_below = max(results)[2]
    for ln in lines:
        ln.used = False
    return [_make_offer(p, group, lines, small, page_no) for _, p, group in _assign(main, names, lines, best_below)]


def _assign(main: list[Line], names: list[Line], lines: list[Line], below: bool) -> list[tuple[float, Line, list[Line]]]:
    """Abbinamento globale prezzo-nome: prima le coppie più vicine."""
    out = []
    pending = list(main)
    for _ in range(len(main)):
        options = []
        snapshot = [ln.used for ln in lines]
        for p in pending:
            group = _pick_name(p, names, lines, below)
            for ln, u in zip(lines, snapshot):
                ln.used = u                  # _pick_name può segnare le varianti: si decide dopo
            if group:
                d = _name_distance(p, group[0] if below else group[-1], below) or 0.0
                options.append((d, p, group))
        if not options:
            break
        d, p, group = min(options, key=lambda t: t[0])
        group = _pick_name(p, names, lines, below)
        pending.remove(p)
        for g in group:
            g.used = True
        out.append((d, p, group))
    return out


def _make_offer(p: Line, group: list[Line], lines: list[Line], small: list[Line], page_no: int) -> OcrOffer:
    raw = " ".join(g.text for g in group)
    name, desc = split_format(raw)
    mult = re.search(r"\s(\d{1,2}\s?x)\s*$", name, re.I)
    if mult:
        n_ = re.sub(r"\D", "", mult.group(1))
        name, desc = name[:mult.start()], f"{n_} x {desc}".strip()
    tx0, ty0 = min(g.x0 for g in group + [p]), min(g.y0 for g in group + [p])
    tx1, ty1 = max(g.x1 for g in group + [p]), max(g.y1 for g in group + [p])
    pad = 0.4 * p.h
    zone = (tx0 - pad, ty0 - 0.3 * p.h, tx1 + pad, ty1 + 0.45 * p.h)
    fmts = _near(lines, "format", zone)
    for f in fmts:
        f.used = True
    parts = [x for x in [desc, *(split_format(f.text)[1] or f.text for f in fmts)] if x]
    seen, uniq = set(), []
    for x in " ".join(parts).replace(" G", " g").split("  "):
        for piece in re.findall(r"\d+(?:[,.]\d+)?\s?(?:x\s?\d+\s?)?[a-zA-Z]+(?:/\d+)?|\d{2,4}/\d{2,4}|[A-Za-z]+", x):
            key = normalize(re.sub(r"(\d+)[.,](\d*?)0*(?=\D|$)", lambda m: m.group(1) + ("," + m.group(2) if m.group(2) else ""),
                                   piece)).replace(" ", "").replace("lt", "l")
            if key and key not in seen:
                seen.add(key)
                uniq.append(piece.replace("1.5", "1,5") if re.match(r"\d+\.\d", piece) else piece)
    desc = " ".join(uniq)
    units = _near(lines, "unit", zone)
    unit_text, per = "", ""
    for u in units:
        u.used = True
        low = u.text.lower().replace("alkg", "al kg").replace("alpezzo", "al pezzo")
        c = parse_price(re.sub(r"[^\d,.]", " ", low).strip().split(" ")[-1]) if re.search(r"\d", low) else None
        word = "al kg" if "kg" in low or "kilo" in low or "chilo" in low else ("al litro" if re.search(r"\bl(t|itro)?\b", low)
                                                                            else ("al pezzo" if "pez" in low or "pz" in low else ""))
        if c and word and word != "al pezzo" and c != p.cents:
            unit_text = f"€ {c // 100},{c % 100:02d} {word}"
        elif word:
            per = word
    if per and per not in desc and not unit_text:
        desc = (desc + " " + per).strip()
    # prezzo barrato: un prezzo piccolo più alto, vicino al prezzo principale
    old = None
    for s in small:
        if (s.cents or 0) > p.cents and math.dist((s.cx, s.cy), (p.cx, p.cy)) < 4 * p.h and not s.used:
            old = s.cents
            s.used = True
            break
    if re.search(r"(?<![a-z])l'\s?etto\b|\(hg\)|\bhg\b", raw, re.I):
        name = re.sub(r"\s*(?<![a-z])l'\s?etto\s*(\(hg\))?|\s*\(hg\)", " ", name, flags=re.I)
        desc = (desc + " all'etto").strip()
    nice = nice_name(name) if name else ""
    bbox = [round(max(0.0, tx0 - 0.005), 4), round(max(0.0, ty0 - 0.005), 4),
            round(min(1.0, tx1 + 0.005), 4), round(min(1.0, ty1 + 0.005), 4)]
    return OcrOffer(page=page_no, name=nice, description=desc.strip(), price_cents=p.cents, old_price_cents=old,
                    unit_price_text=unit_text, bbox=bbox, photo_bbox=None, price_line=p, lines=group)


# ------------------------------------------------------------------ seconda lettura del prezzo

def reread_once(page: pdfdoc.Page, line: Line, factor: float, trim_left: float = 0.0) -> int | None:
    """Rilegge il solo prezzo su un ritaglio ingrandito (trim_left: quanto togliere a sinistra)."""
    w, h = page.rect.width, page.rect.height
    pad_x, pad_y = 0.35 * (line.x1 - line.x0), 0.35 * (line.y1 - line.y0)
    left = line.x0 + trim_left * (line.x1 - line.x0) - (0 if trim_left else pad_x)
    clip = pdfdoc.Rect(max(0, left) * w, max(0, line.y0 - pad_y) * h,
                        min(1, line.x1 + pad_x) * w, min(1, line.y1 + pad_y) * h)
    rgb = render(page, max_side=int(max(160, min(1100, factor * max(clip.width, clip.height)))), clip=clip)
    # altezza attesa del prezzo nel ritaglio: un prezzo molto più piccolo (barrato, al kg) non vale
    expected = (line.y1 - line.y0) * h / max(1e-6, clip.height) * rgb.shape[0]
    found = []
    for box, text, score in run_ocr(rgb):
        t = clean(text)
        m = _PRICE_ONLY.match(t.replace(" ", ""))
        ys = [pt[1] for pt in box]
        if m and score >= 0.6 and (max(ys) - min(ys)) >= 0.6 * expected:
            found.append(int(m.group(1)) * 100 + int(m.group(2)))
    return found[0] if len(set(found)) == 1 else None


# ------------------------------------------------------------------ la foto del prodotto

def _walls(small: np.ndarray, soft: bool | None = None) -> np.ndarray:
    """Linee lunghe e sottili della pagina (bordi delle caselle): il ritaglio non le attraversa.
    soft=True vede anche i bordi grigio chiaro; None sceglie la sensibilità che trova più caselle."""
    import cv2
    if soft is None:
        best = max((_walls(small, False), _walls(small, True)), key=lambda wl: _count_cells(wl))
        return best
    h, w = small.shape[:2]
    gray = cv2.cvtColor(small, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 20, 60) if soft else cv2.Canny(gray, 60, 160)
    hor = cv2.morphologyEx(edges, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (max(10, w // 6), 1)))
    ver = cv2.morphologyEx(edges, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(10, h // 6))))
    return cv2.dilate(hor | ver, np.ones((3, 3), np.uint8)) > 0


def _count_cells(walls: np.ndarray) -> int:
    """Quante caselle "buone" (né minuscole né grandi come mezza pagina) formano questi bordi."""
    import cv2
    n, lab = cv2.connectedComponents((~walls).astype(np.uint8), connectivity=4)
    area = np.bincount(lab.ravel(), minlength=n)[1:]
    total = walls.size
    return int(((area > 0.003 * total) & (area < 0.2 * total)).sum())


def _cut_text(box: list[int], text: np.ndarray, mass: np.ndarray) -> list[int]:
    """Restringe il riquadro finché non contiene più scritte, tagliando dal lato che fa perdere meno prodotto."""
    x0, y0, x1, y1 = box
    for _ in range(6):
        t = text[y0:y1, x0:x1]
        if t.sum() <= 0.01 * max(1, (x1 - x0) * (y1 - y0)):
            break
        ys, xs = np.nonzero(t)
        tx0, tx1, ty0, ty1 = x0 + xs.min(), x0 + xs.max() + 1, y0 + ys.min(), y0 + ys.max() + 1
        options = []
        for cand in ([x0, y0, tx0, y1], [tx1, y0, x1, y1], [x0, y0, x1, ty0], [x0, ty1, x1, y1]):
            cx0, cy0, cx1, cy1 = cand
            if cx1 - cx0 < 12 or cy1 - cy0 < 12:
                continue
            options.append((mass[cy0:cy1, cx0:cx1].sum(), cand))
        if not options:
            return [x0, y0, x0, y0]
        x0, y0, x1, y1 = max(options, key=lambda t: t[0])[1]
    return [x0, y0, x1, y1]


# Dove può stare la foto rispetto a nome e prezzo. Nei volantini la foto non sta mai sotto il suo prezzo.
_DIRS = {"sinistra": (-1.0, 0.0), "sopra-sinistra": (-0.75, -0.75), "sopra": (0.0, -1.0),
         "sopra-destra": (0.75, -0.75), "destra": (1.0, 0.0)}


def find_photos(rgb: np.ndarray, offers: list[OcrOffer], lines: list[Line]) -> None:
    """La foto di ogni prodotto, come la ritaglierebbe un grafico.

    1. Si capisce dove stanno le foto rispetto alle didascalie in questa pagina (di solito sopra
       o a sinistra del nome): è una scelta di impaginazione, uguale per tutta la pagina.
    2. Si mette un "segnaposto" dove dovrebbe stare la foto di ogni offerta e lo spazio si divide
       tra i segnaposto: ogni zona contiene una foto sola.
    3. Nella zona si tiene ciò che non è sfondo, senza le didascalie del volantino (le scritte
       stampate sulle confezioni invece restano: sono parte del prodotto).
    """
    import cv2
    if not offers:
        return
    H, W = rgb.shape[:2]
    k = 800 / max(H, W)
    small = cv2.resize(rgb, (max(1, int(W * k)), max(1, int(H * k))), interpolation=cv2.INTER_AREA)
    h, w = small.shape[:2]
    img = small.astype(np.int16)
    name_h = float(np.median([g.h for o in offers for g in o.lines])) if any(o.lines for o in offers) else 0.01
    captions = [ln for ln in lines if ln.used or ln.kind in ("price", "unit")
                or (ln.kind == "noise" and ln.h > 1.8 * name_h)]          # titoli di reparto e slogan
    text = np.zeros((h, w), bool)
    for ln in captions:
        m = 0.25 * ln.h
        text[max(0, int((ln.y0 - m) * h)):int((ln.y1 + m) * h) + 1, max(0, int((ln.x0 - m) * w)):int((ln.x1 + m) * w) + 1] = True
    walls = _walls(small)
    # caselle chiuse dai bordi: zone separate dalle linee
    n_cells, cells = cv2.connectedComponents((~walls).astype(np.uint8), connectivity=4)
    cell_area = np.bincount(cells.ravel(), minlength=n_cells)
    # ciò che non è sfondo: lontano dal colore medio della zona, oppure colorato e diverso dalla pagina
    blur = cv2.GaussianBlur(small, (0, 0), 30).astype(np.int16)
    page_bg = np.median(img.reshape(-1, 3), axis=0)
    sat = img.max(axis=2) - img.min(axis=2)
    mass = ((np.abs(img - blur).sum(axis=2) > 50) | ((sat > 60) & (np.abs(img - page_bg).sum(axis=2) > 80)))
    mass &= img.sum(axis=2) < 735                     # il bianco della carta non è prodotto
    mass &= ~text & ~walls
    mass = cv2.morphologyEx(mass.astype(np.uint8), cv2.MORPH_CLOSE,
                            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (max(3, w // 100),) * 2)) > 0
    mass &= ~walls
    integral = cv2.integral(mass.astype(np.uint8))

    def density(cx: float, cy: float, half: float) -> float:
        x0, x1 = int(max(0, cx - half)), int(min(w, cx + half))
        y0, y1 = int(max(0, cy - half)), int(min(h, cy + half))
        if x1 <= x0 or y1 <= y0:
            return 0.0
        tot = integral[y1, x1] - integral[y0, x1] - integral[y1, x0] + integral[y0, x0]
        return float(tot) / ((x1 - x0) * (y1 - y0))

    centers = np.array([[(o.bbox[0] + o.bbox[2]) / 2 * w, (o.bbox[1] + o.bbox[3]) / 2 * h] for o in offers])
    if len(offers) > 1:
        dd = np.sqrt(((centers[:, None] - centers[None]) ** 2).sum(-1))
        np.fill_diagonal(dd, np.inf)
        spacing = float(np.median(dd.min(axis=1)))
    else:
        spacing = 0.45 * min(w, h)
    spacing = max(spacing, 0.08 * min(w, h))
    half = 0.38 * spacing
    # 1) direzione delle foto rispetto alle didascalie, per la pagina intera
    tboxes = [(o.bbox[0] * w, o.bbox[1] * h, o.bbox[2] * w, o.bbox[3] * h) for o in offers]

    def hits_other(i: int, x0: float, y0: float, x1: float, y1: float) -> bool:
        return any(j != i and t[0] < x1 and t[2] > x0 and t[1] < y1 and t[3] > y0 for j, t in enumerate(tboxes))

    per_offer = []
    for i, (cx, cy) in enumerate(centers):
        dens = {}
        for d, v in _DIRS.items():
            px, py = cx + v[0] * 0.75 * spacing, cy + v[1] * 0.75 * spacing
            val = density(px, py, half)
            if hits_other(i, px - half, py - half, px + half, py + half):
                val *= 0.15            # lì c'è la didascalia di un altro prodotto: non è la nostra foto
            dens[d] = val
        per_offer.append(dens)
    page_dir = max(_DIRS, key=lambda d: sum(p[d] for p in per_offer))
    anchors = []
    for (cx, cy), p in zip(centers, per_offer):
        d = page_dir if p[page_dir] >= 0.6 * max(p.values()) else max(p, key=p.get)
        v = _DIRS[d]
        anchors.append((cx + v[0] * 0.7 * spacing, cy + v[1] * 0.7 * spacing))
    anchors = np.array(anchors)
    # 2) lo spazio si divide tra i segnaposto delle foto (e le didascalie restano a chi appartengono)
    gy, gx = np.mgrid[0:h, 0:w]
    d2 = (gx[None] - anchors[:, 0, None, None]) ** 2 + (gy[None] - anchors[:, 1, None, None]) ** 2
    owner = d2.argmin(axis=0)
    for idx, o in enumerate(offers):
        ax, ay = anchors[idx]
        cx, cy = int(min(w - 1, centers[idx][0])), int(min(h - 1, centers[idx][1]))
        cell = cells[cy, cx]
        others_in_cell = sum(1 for j, (ox, oy) in enumerate(centers)
                             if j != idx and cells[int(min(h - 1, oy)), int(min(w - 1, ox))] == cell)
        if cell != 0 and cell_area[cell] < 0.2 * w * h and others_in_cell == 0:
            # l'offerta è in una casella tutta sua: la foto è ciò che c'è nella casella
            mine = mass & (cells == cell)
            ax, ay = float(np.mean(np.nonzero(cells == cell)[1])), float(np.mean(np.nonzero(cells == cell)[0]))
        else:
            win = (np.abs(gx - ax) <= 1.1 * spacing) & (np.abs(gy - ay) <= 1.1 * spacing)
            mine = mass & (owner == idx) & win
        # 3) l'oggetto principale: la componente più grande vicina al segnaposto, con i suoi pezzi
        tb = [o.bbox[0] * w, o.bbox[1] * h, o.bbox[2] * w, o.bbox[3] * h]
        n, lab, stats, cent = cv2.connectedComponentsWithStats(mine.astype(np.uint8), connectivity=8)
        o.photo_bbox = None
        if n <= 1:
            o.card_bbox = _card(tb, None, (ax, ay), spacing, cells, cell, w, h)        # type: ignore[attr-defined]
            continue
        def gap(r: tuple, t: tuple) -> float:
            return math.hypot(max(0.0, t[0] - r[2], r[0] - t[2]), max(0.0, t[1] - r[3], r[1] - t[3]))

        scores = []
        for c in range(1, n):
            cx_, cy_, cw_, ch_ = (float(v) for v in stats[c, :4])
            r = (cx_, cy_, cx_ + cw_, cy_ + ch_)
            g_own = gap(r, tb)
            g_other = min((gap(r, t) for j, t in enumerate(tboxes) if j != idx), default=1e9)
            if g_other + 0.02 * spacing < 0.8 * g_own:
                scores.append(0.0)                 # è attaccato alla didascalia di un altro prodotto
                continue
            scores.append(stats[c, cv2.CC_STAT_AREA] / (1 + 4.0 * g_own / spacing))
        if max(scores) <= 0:
            o.card_bbox = _card(tb, None, (ax, ay), spacing, cells, cell, w, h)        # type: ignore[attr-defined]
            continue
        main = 1 + int(np.argmax(scores))
        if stats[main, cv2.CC_STAT_AREA] < 0.06 * spacing * spacing:
            o.card_bbox = _card(tb, None, (ax, ay), spacing, cells, cell, w, h)        # type: ignore[attr-defined]
            continue
        keep = lab == main
        mx, my, mw, mh = (int(v) for v in stats[main, :4])
        for c in range(1, n):
            if c != main and stats[c, cv2.CC_STAT_AREA] > 0.08 * stats[main, cv2.CC_STAT_AREA]:
                cx_, cy_ = cent[c]
                if mx - 0.15 * mw <= cx_ <= mx + 1.15 * mw and my - 0.15 * mh <= cy_ <= my + 1.15 * mh:
                    keep |= lab == c
        ys, xs = np.nonzero(keep)
        photo = [int(np.percentile(xs, 1)), int(np.percentile(ys, 1)), int(np.percentile(xs, 99)) + 1,
                 int(np.percentile(ys, 99)) + 1]
        o.card_bbox = _card(tb, photo, (ax, ay), spacing, cells, cell, w, h)          # type: ignore[attr-defined]
        # Foto "pulita" solo se è nettamente separata: nessuna didascalia dentro, forma compatta,
        # tutta dentro il riquadro dell'offerta. Altrimenti si usa il riquadro intero del volantino.
        px0, py0, px1, py1 = photo
        pw, ph_ = px1 - px0, py1 - py0
        inside_text = text[py0:py1, px0:px1].mean() if pw > 0 and ph_ > 0 else 1.0
        fill = keep[py0:py1, px0:px1].mean() if pw > 0 and ph_ > 0 else 0.0
        cb = o.card_bbox
        within = (px0 >= cb[0] * w - 2 and py0 >= cb[1] * h - 2 and px1 <= cb[2] * w + 2 and py1 <= cb[3] * h + 2)
        if inside_text < 0.01 and fill > 0.45 and within and min(pw, ph_) > 0.3 * spacing and max(pw, ph_) < 3 * min(pw, ph_):
            pad = int(0.04 * max(pw, ph_))
            o.photo_bbox = [round(max(0, px0 - pad) / w, 4), round(max(0, py0 - pad) / h, 4),
                            round(min(w, px1 + pad) / w, 4), round(min(h, py1 + pad) / h, 4)]
    for i, o in enumerate(offers):
        if getattr(o, "card_bbox", None):
            o.card_bbox = _without_others(o.card_bbox, tboxes[i], [t for j, t in enumerate(tboxes) if j != i], w, h)


def _without_others(card: list[float], own: tuple, others: list[tuple], w: int, h: int) -> list[float]:
    """Toglie dal riquadro le didascalie delle altre offerte, tagliando dal lato giusto."""
    x0, y0, x1, y1 = card[0] * w, card[1] * h, card[2] * w, card[3] * h
    for _ in range(8):
        hit = [t for t in others if t[0] < x1 and t[2] > x0 and t[1] < y1 and t[3] > y0]
        if not hit:
            break
        t = max(hit, key=lambda t: (min(x1, t[2]) - max(x0, t[0])) * (min(y1, t[3]) - max(y0, t[1])))
        cands = []
        if t[2] <= own[0]:
            cands.append((t[2] + 2, y0, x1, y1))           # l'altra è a sinistra: si taglia a sinistra
        if t[0] >= own[2]:
            cands.append((x0, y0, t[0] - 2, y1))
        if t[3] <= own[1]:
            cands.append((x0, t[3] + 2, x1, y1))
        if t[1] >= own[3]:
            cands.append((x0, y0, x1, t[1] - 2))
        if not cands:
            break
        x0, y0, x1, y1 = max(cands, key=lambda c: (c[2] - c[0]) * (c[3] - c[1]))
    return [round(x0 / w, 4), round(y0 / h, 4), round(x1 / w, 4), round(y1 / h, 4)]


def _card(tb: list[float], photo: list[int] | None, anchor: tuple[float, float], spacing: float,
          cells: np.ndarray, cell: int, w: int, h: int) -> list[float]:
    """Il riquadro dell'offerta come l'ha impaginata il grafico del volantino: foto e didascalia."""
    if photo is None:
        ax, ay = anchor
        half = 0.42 * spacing
        photo = [ax - half, ay - half, ax + half, ay + half]
    x0, y0 = min(tb[0], photo[0]), min(tb[1], photo[1])
    x1, y1 = max(tb[2], photo[2]), min(max(tb[3], photo[3]), tb[3] + 0.15 * spacing)
    pad = 0.03 * max(x1 - x0, y1 - y0)
    x0, y0, x1, y1 = x0 - pad, y0 - pad, x1 + pad, y1 + pad
    if cell:
        ys, xs = np.nonzero(cells == cell)
        if len(xs) and len(xs) < 0.2 * w * h:          # nella casella: mai oltre i suoi bordi
            x0, y0 = max(x0, xs.min()), max(y0, ys.min())
            x1, y1 = min(x1, xs.max() + 1), min(y1, ys.max() + 1)
    x0, y0, x1, y1 = max(0.0, x0), max(0.0, y0), min(float(w), x1), min(float(h), y1)
    return [round(x0 / w, 4), round(y0 / h, 4), round(x1 / w, 4), round(y1 / h, 4)]


# ------------------------------------------------------------------ la pagina intera

@dataclass
class PageReading:
    offers: list[OcrOffer]
    text: str                          # tutto il testo letto (per date di validità e titolo)
    lines: list[Line]


def look_closer(page: pdfdoc.Page, lines: list[Line], offers: list[OcrOffer]) -> list[Line]:
    """Per i nomi rimasti senza prezzo: ingrandisce la zona intorno e cerca il prezzo lì."""
    main_h = [o.price_line.h for o in offers]
    name_h = [g.h for o in offers for g in o.lines]
    if not main_h or not name_h:
        return []
    ph, nh = float(np.median(main_h)), float(np.median(name_h))
    # solo righe che sembrano davvero il nome di un prodotto: stessa altezza dei nomi già trovati,
    # in maiuscolo come gli altri, fuori dai riquadri delle offerte già lette
    upper_style = sum(_is_upper(g.text) for o in offers for g in o.lines) >= 0.6 * len(name_h)
    names = [ln for ln in lines if ln.kind == "name" and not ln.used and len(ln.text) >= 4
             and 0.6 * nh <= ln.h <= 1.6 * nh and (not upper_style or _is_upper(ln.text))
             and not any(o.bbox[0] <= ln.cx <= o.bbox[2] and o.bbox[1] <= ln.cy <= o.bbox[3] for o in offers)]
    names = sorted(names, key=lambda n: -n.score)[:14]
    if not names:
        return []
    found: list[Line] = []
    w, h = page.rect.width, page.rect.height
    for n in names:
        x0, x1 = max(0.0, n.x0 - 1.8 * max(n.w, 2 * ph)), min(1.0, n.x1 + 0.6 * max(n.w, ph))
        y0, y1 = max(0.0, n.y0 - 0.5 * ph), min(1.0, n.y1 + 2.2 * ph)
        clip = pdfdoc.Rect(x0 * w, y0 * h, x1 * w, y1 * h)
        rgb = render(page, max_side=int(max(400, min(1400, 900 * (x1 - x0) / max(1e-6, ph * 2)))), clip=clip)
        for ln in _lines_from(rgb, x0, y0, x1 - x0, y1 - y0):
            classify(ln)
            if ln.kind != "price" or ln.h < 0.5 * ph:
                continue
            if any(_iou(ln, o.price_line) > 0.2 or (abs(ln.cx - o.price_line.cx) < ph and abs(ln.cy - o.price_line.cy) < ph)
                   for o in offers) or any(_iou(ln, f) > 0.2 for f in found):
                continue
            found.append(ln)
    return found


def _euro_as_digit(line: Line) -> int | None:
    """ "61,69" senza simbolo dell'euro: forse il "6" è il simbolo € stilizzato. Restituisce 1,69."""
    if line.cents is None or "€" in line.text or line.cents < 1000:
        return None
    euros = str(line.cents // 100)
    if euros[0] not in "6890" or len(euros) < 2:
        return None
    return int(euros[1:]) * 100 + line.cents % 100


def reread_price(page: pdfdoc.Page, line: Line) -> tuple[bool, int | None]:
    """Nuove letture del prezzo su ritagli ingranditi. Restituisce (confermato, lettura alternativa)."""
    a = reread_once(page, line, 6)
    if a == line.cents:
        return True, None
    b = reread_once(page, line, 9)
    if b == line.cents and a is None:
        return True, None
    if a is not None and a == b and a != line.cents:
        return False, a
    guess = _euro_as_digit(line)
    if guess is not None:
        for trim in (0.2, 0.28):
            if reread_once(page, line, 7, trim_left=trim) == guess:
                return False, guess
    return False, None


def measure_busy(lines: list[Line], rgb: np.ndarray) -> None:
    """Per ogni riga: quanto varia l'immagine nella cornice intorno (didascalia su fondo pulito
    oppure scritta sopra una foto o un disegno, come quelle stampate sulle confezioni)."""
    H, W = rgb.shape[:2]
    gray = rgb.mean(axis=2)
    for ln in lines:
        m = max(0.6 * ln.h, 0.004)
        x0, y0 = max(0, int((ln.x0 - m) * W)), max(0, int((ln.y0 - m) * H))
        x1, y1 = min(W, int((ln.x1 + m) * W) + 1), min(H, int((ln.y1 + m) * H) + 1)
        ix0, iy0, ix1, iy1 = int(ln.x0 * W), int(ln.y0 * H), int(ln.x1 * W) + 1, int(ln.y1 * H) + 1
        ring = np.ones((y1 - y0, x1 - x0), bool)
        ring[max(0, iy0 - y0):max(0, iy1 - y0), max(0, ix0 - x0):max(0, ix1 - x0)] = False
        vals = gray[y0:y1, x0:x1][ring]
        ln.busy = float(min(1.0, vals.std() / 60)) if vals.size > 10 else 0.0


def read_page(page: pdfdoc.Page, page_no: int, confirm: bool = True) -> PageReading:
    lines, rgb = read_lines(page)
    _CELLS.value = Cells(rgb)
    measure_busy(lines, rgb)
    text = "\n".join(ln.text for ln in sorted(lines, key=lambda ln: (round(ln.y0, 2), ln.x0)))
    offers = lines_to_offers(lines, page_no)
    extra = look_closer(page, lines, offers)
    if extra:
        lines.extend(extra)
        offers += lines_to_offers_from(extra, lines, page_no, offers)
    find_photos(rgb, offers, lines)
    for o in offers:
        card = getattr(o, "card_bbox", None) or o.bbox
        o.erase = [[ln.x0, ln.y0, ln.x1, ln.y1] for ln in lines                       # type: ignore[attr-defined]
                   if card[0] <= ln.cx <= card[2] and card[1] <= ln.cy <= card[3]
                   and (ln.kind in ("price", "unit", "format") or (ln.kind == "name" and ln.used)
                        or (ln.kind == "noise" and "%" in ln.text and len(ln.text) <= 6))]
    for o in offers:
        o.confirmed = False                                                        # type: ignore[attr-defined]
        o.alternative = None                                                       # type: ignore[attr-defined]
    if confirm:
        for o in offers:
            ok, alt = reread_price(page, o.price_line)
            o.confirmed = ok                                                       # type: ignore[attr-defined]
            if alt is not None and 0 < alt <= 1_000_000:
                # due letture ingrandite e concordi danno un altro prezzo: si propone quello,
                # ma resta "da controllare" e si segnala anche la prima lettura
                o.alternative, o.price_cents = o.price_cents, alt                  # type: ignore[attr-defined]
    return PageReading(offers=offers, text=text, lines=lines)


def lines_to_offers_from(prices: list[Line], lines: list[Line], page_no: int,
                         offers_hint: list[OcrOffer] | None = None) -> list[OcrOffer]:
    """Offerte dai prezzi trovati guardando più da vicino (le righe sono già classificate)."""
    names = [ln for ln in lines if ln.kind == "name" and not ln.used]
    small: list[Line] = []
    out = []
    below = sum(1 for o in offers_hint if o.lines and o.lines[0].cy > o.price_line.cy) > len(offers_hint) / 2 \
        if offers_hint else False
    for p in prices:
        group = _pick_name(p, names, lines, below)
        if not group:
            continue
        for g in group:
            g.used = True
        out.append(_make_offer(p, group, lines, small, page_no))
    return out


def to_category(name: str, description: str) -> str:
    return coerce_category(None, name, description)


def similar_names(a: str, b: str) -> bool:
    return normalize(a) == normalize(b)


__all__ = ["available", "read_page", "PageReading", "OcrOffer", "OcrUnavailable", "discount_percent",
           "to_category", "similar_names", "Image"]
