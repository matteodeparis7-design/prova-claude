"""Radar del quartiere: le offerte del negozio confrontate con i volantini dei concorrenti in zona.

- I volantini dei concorrenti si leggono con lo stesso lettore (prezzi controllati allo stesso modo).
- Due offerte si confrontano solo se sono lo stesso prodotto o un prodotto equivalente:
  stesse parole importanti nel nome, stessa categoria, formati confrontabili.
- Se i formati sono diversi si confronta il prezzo al kg o al litro (calcolato, mai inventato).
- Il risultato serve al negoziante per scegliere cosa mettere in evidenza: i nomi dei concorrenti
  non finiscono mai nei testi pubblici (la pubblicità comparativa ha regole precise).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models import Flyer, FlyerStatus, Offer, Store
from ...money import format_eur

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


@dataclass
class Match:
    own: Offer
    other: Offer
    competitor: str
    same_brand: bool
    similarity: float
    own_unit: float          # centesimi per unità confrontabile
    other_unit: float
    unit_label: str

    @property
    def diff_pct(self) -> float:
        """Positivo = il negozio costa meno del concorrente."""
        return (self.other_unit - self.own_unit) / self.other_unit * 100 if self.other_unit else 0.0

    @property
    def verdict(self) -> str:
        d = self.diff_pct
        return "meno caro" if d >= 2 else "più caro" if d <= -2 else "uguale"


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


def compare(own: list[Offer], others: list[tuple[str, Offer]], threshold: float = 0.62) -> list[Match]:
    """Per ogni offerta del negozio, il confronto migliore con ciascun concorrente."""
    out: list[Match] = []
    for o in own:
        pu = per_unit(o)
        if pu is None:
            continue
        best: dict[str, Match] = {}
        for comp, x in others:
            sim = similarity(o, x)
            if sim < threshold:
                continue
            px = per_unit(x)
            if px is None or px[1] != pu[1]:
                continue
            qo, qx = quantity(o.description or ""), quantity(x.description or "")
            if qo and qx and qo.kind == qx.kind and max(qo.amount, qx.amount) / max(1.0, min(qo.amount, qx.amount)) > 4:
                continue      # formati troppo diversi (es. 100 g contro 1 kg): non è la stessa spesa
            m = Match(own=o, other=x, competitor=comp, same_brand=bool(_brand(o)) and _brand(o) == _brand(x),
                      similarity=round(sim, 3), own_unit=pu[0], other_unit=px[0], unit_label=pu[1])
            if comp not in best or m.similarity > best[comp].similarity:
                best[comp] = m
        out.extend(best.values())
    return out


def _overlaps(a: Flyer, b: Flyer) -> bool:
    if not (a.valid_from and a.valid_to and b.valid_from and b.valid_to):
        ref_a = a.valid_from or (a.created_at.date() if a.created_at else date.today())
        ref_b = b.valid_from or (b.created_at.date() if b.created_at else date.today())
        return abs((ref_a - ref_b).days) <= 10
    return a.valid_from <= b.valid_to and b.valid_from <= a.valid_to


def competitor_flyers(session: Session, store: Store, flyer: Flyer | None = None) -> list[Flyer]:
    rows = session.scalars(select(Flyer).where(Flyer.store_id == store.id, Flyer.competitor != "",
                                               Flyer.status == FlyerStatus.ready)
                           .order_by(Flyer.created_at.desc(), Flyer.id.desc())).all()
    if flyer is not None:
        rows = [f for f in rows if _overlaps(flyer, f)]
    # Per ogni concorrente solo il volantino più recente
    seen, out = set(), []
    for f in rows:
        if f.competitor.lower() not in seen:
            seen.add(f.competitor.lower())
            out.append(f)
    return out


def _unit_text(cents: float, label: str) -> str:
    return f"{format_eur(int(round(cents)))} {label}"


def radar(session: Session, store: Store, flyer: Flyer) -> dict:
    comps = competitor_flyers(session, store, flyer)
    others = [(f.competitor, o) for f in comps for o in f.offers]
    matches = compare(list(flyer.offers), others)
    rows = []
    for m in sorted(matches, key=lambda m: -m.diff_pct):
        rows.append({
            "offer_id": m.own.id, "offer": m.own.name, "brand": m.own.brand, "description": m.own.description,
            "price": format_eur(m.own.price_cents), "competitor": m.competitor,
            "competitor_offer": " ".join(x for x in (m.other.brand, m.other.name, m.other.description) if x),
            "competitor_price": format_eur(m.other.price_cents),
            "own_unit": _unit_text(m.own_unit, m.unit_label), "competitor_unit": _unit_text(m.other_unit, m.unit_label),
            "diff_pct": round(m.diff_pct, 1), "verdict": m.verdict, "same_product": m.same_brand,
            "is_featured": m.own.is_featured,
        })
    # Una riga per prodotto nei suggerimenti: conta il confronto meno favorevole (onestà verso il cliente).
    worst: dict[int, dict] = {}
    for r in rows:
        if r["offer_id"] not in worst or r["diff_pct"] < worst[r["offer_id"]]["diff_pct"]:
            worst[r["offer_id"]] = r
    wins = sorted((r for r in worst.values() if r["verdict"] == "meno caro"), key=lambda r: -r["diff_pct"])
    losses = sorted((r for r in worst.values() if r["verdict"] == "più caro"), key=lambda r: r["diff_pct"])
    return {
        "competitors": [{"flyer_id": f.id, "name": f.competitor, "offers": len(f.offers),
                         "valid_from": f.valid_from.isoformat() if f.valid_from else None,
                         "valid_to": f.valid_to.isoformat() if f.valid_to else None} for f in comps],
        "rows": rows,
        "summary": {"compared": len(worst), "cheaper": len(wins), "dearer": len(losses),
                    "same": len(worst) - len(wins) - len(losses)},
        "suggest_feature": [r["offer_id"] for r in wins[:4]],
        "wins": wins[:6], "losses": losses[:6],
    }


def stale_competitors(session: Session, store: Store, today: date | None = None) -> list[Flyer]:
    """Volantini dei concorrenti scaduti da più di una settimana (da sostituire con quelli nuovi)."""
    today = today or date.today()
    rows = session.scalars(select(Flyer).where(Flyer.store_id == store.id, Flyer.competitor != "")).all()
    return [f for f in rows if f.valid_to and f.valid_to < today - timedelta(days=7)]
