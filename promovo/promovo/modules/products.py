"""Prodotti: parole importanti del nome, quantità della confezione, prezzo al kg o al litro, somiglianza.

Serve a confrontare le offerte **dello stesso negozio** (storico dei prezzi per l'Omnibus, cartellini, Correttore,
Salvaspreco, Parola alla cassa). Promovo non usa i prezzi di altri negozi.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from ..models import Offer

STOP = {"di", "da", "del", "della", "dei", "delle", "al", "alla", "allo", "ai", "agli", "alle", "con", "in", "per", "e",
        "ed", "il", "la", "lo", "i", "gli", "le", "un", "una", "uno", "a", "o", "tipo", "gusto", "gusti", "vari",
        "varie", "assortiti", "assortite", "assortito", "conf", "confezione", "pz", "pezzi", "x", "offerta", "fresco",
        "fresca", "freschi", "fresche", "classico", "classica", "classici", "classiche", "nuovo", "nuova", "formato"}
UNIT_WORDS = {"g", "gr", "grammi", "kg", "chilo", "chili", "ml", "cl", "l", "lt", "litro", "litri", "lavaggi", "pz"}


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def tokens(text: str) -> set[str]:
    t = _strip_accents((text or "").lower())
    t = re.sub(r"\d+[.,]?\d*", " ", t)
    words = re.findall(r"[a-z]+", t)
    out = set()
    for w in words:
        if w in STOP or w in UNIT_WORDS or len(w) < 3:
            continue
        # singolare e plurale contano uguali: mela/mele, spaghetto/spaghetti
        out.add(w[:-1] if len(w) >= 4 and w[-1] in "aeio" else w)
    return out


@dataclass
class Quantity:
    amount: float      # grammi o millilitri (o numero di lavaggi/pezzi)
    kind: str          # "massa" | "volume" | "lavaggi" | "pezzi"


_Q = re.compile(r"(?:(\d+)\s*[x×]\s*)?(\d+(?:[.,]\d+)?)\s*(kg|g|gr|grammi|l|lt|litri|litro|cl|ml|lavaggi|pz|pezzi)\b",
                re.IGNORECASE)


def quantity(text: str) -> Quantity | None:
    """Quantità totale della confezione: "4 x 175 g" -> 700 g; "6 x 1,5 L" -> 9000 ml; "1 litro" -> 1000 ml."""
    m = _Q.search(text or "")
    if not m:
        return None
    mult = int(m.group(1)) if m.group(1) else 1
    n = float(m.group(2).replace(",", "."))
    unit = m.group(3).lower()
    if unit in ("kg",):
        return Quantity(mult * n * 1000, "massa")
    if unit in ("g", "gr", "grammi"):
        return Quantity(mult * n, "massa")
    if unit in ("l", "lt", "litri", "litro"):
        return Quantity(mult * n * 1000, "volume")
    if unit == "cl":
        return Quantity(mult * n * 10, "volume")
    if unit == "ml":
        return Quantity(mult * n, "volume")
    if unit == "lavaggi":
        return Quantity(mult * n, "lavaggi")
    return Quantity(mult * n, "pezzi")


def per_unit(o: Offer) -> tuple[float, str] | None:
    """Prezzo confrontabile: (centesimi per kg / litro / lavaggio / pezzo, etichetta), oppure None."""
    text = " ".join(x for x in (o.description, o.name, o.unit_price_text) if x)
    if re.search(r"\bal\s*(kg|chilo)\b", text, re.I) and not quantity(o.description or ""):
        return float(o.price_cents), "al kg"
    if re.search(r"\bal\s*(l|litro)\b", text, re.I) and not quantity(o.description or ""):
        return float(o.price_cents), "al litro"
    q = quantity(o.description or "") or quantity(o.name)
    if q is None or q.amount <= 0:
        return None
    if q.kind == "massa":
        return o.price_cents * 1000 / q.amount, "al kg"
    if q.kind == "volume":
        return o.price_cents * 1000 / q.amount, "al litro"
    if q.kind == "lavaggi":
        return o.price_cents / q.amount, "a lavaggio"
    return o.price_cents / q.amount, "al pezzo"


def _brand(o: Offer) -> str:
    return _strip_accents((o.brand or "").lower()).strip()


def similarity(a: Offer, b: Offer) -> float:
    ta, tb = tokens(a.name), tokens(b.name)
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    if inter == 0:
        return 0.0
    # quanto del nome più corto si ritrova nell'altro (es. "spaghetti" in "spaghetti di grano duro")
    contain = inter / min(len(ta), len(tb))
    jacc = inter / len(ta | tb)
    s = 0.6 * contain + 0.4 * jacc
    if a.category and b.category and a.category != b.category and "altro" not in (a.category, b.category):
        s *= 0.5
    ba, bb = _brand(a), _brand(b)
    if ba and bb and ba != bb:
        s *= 0.85             # marca diversa: prodotto equivalente, non lo stesso
    return s
