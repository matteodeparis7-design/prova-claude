"""Agente Omnibus: controlla i prezzi barrati con lo storico dei volantini del negozio.

Regola (art. 17-bis del Codice del Consumo, direttiva Omnibus): quando si annuncia uno sconto, il prezzo
«prima» da indicare è il più basso praticato nei 30 giorni precedenti la riduzione.
Promovo conosce i volantini che il negozio ha già caricato: se nei 30 giorni prima lo stesso prodotto
era in offerta a un prezzo più basso del prezzo barrato di adesso, lo segnala, con il prezzo da indicare
e lo sconto vero. Non cambia mai niente da solo: avvisa, e decide il negoziante.

Limiti, detti chiaramente: Promovo vede solo i volantini caricati (non i prezzi di cassa fuori volantino),
e per le riduzioni progressive della stessa promozione la legge prevede regole particolari.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Flyer, FlyerStatus, Offer, Store
from ..money import discount_percent, format_eur
from .radar.service import per_unit, quantity, similarity

WINDOW_DAYS = 30


@dataclass
class Finding:
    offer: Offer
    previous: Offer
    previous_flyer: Flyer
    lowest_cents: int          # il prezzo più basso dei 30 giorni, nello stesso formato dell'offerta

    @property
    def true_discount(self) -> int:
        return discount_percent(self.offer.price_cents, self.lowest_cents) or 0

    def as_dict(self) -> dict:
        f = self.previous_flyer
        when = (f"dal {f.valid_from.day}/{f.valid_from.month} al {f.valid_to.day}/{f.valid_to.month}"
                if f.valid_from and f.valid_to else "in un volantino precedente")
        o = self.offer
        if self.lowest_cents <= o.price_cents:
            advice = (f"Nei 30 giorni prima era già a {format_eur(self.lowest_cents)}: non è uno sconto, "
                      "meglio togliere il prezzo barrato e la percentuale.")
        else:
            advice = (f"Il prezzo barrato dovrebbe essere {format_eur(self.lowest_cents)} "
                      f"(sconto vero: -{self.true_discount}%), non {format_eur(o.old_price_cents)}.")
        return {"offer_id": o.id, "name": o.name, "description": o.description,
                "printed_old_cents": o.old_price_cents, "price_cents": o.price_cents,
                "lowest_cents": self.lowest_cents, "true_discount": self.true_discount if self.lowest_cents > o.price_cents else 0,
                "when": when, "flyer_title": f.title or "volantino precedente",
                "message": f"«{o.name}» {when} costava {format_eur(self.lowest_cents)}. {advice}"}


def _start(f: Flyer) -> date:
    return f.valid_from or (f.created_at.date() if f.created_at else date.today())


def previous_flyers(session: Session, store: Store, flyer: Flyer, days: int = WINDOW_DAYS) -> list[Flyer]:
    """I volantini del negozio validi in almeno un giorno dei 30 prima dell'inizio di questo."""
    start = _start(flyer)
    lo, hi = start - timedelta(days=days), start - timedelta(days=1)
    rows = session.scalars(select(Flyer).where(Flyer.store_id == store.id, Flyer.competitor == "",
                                               Flyer.status == FlyerStatus.ready, Flyer.id != flyer.id)).all()
    out = []
    for f in rows:
        a = f.valid_from or _start(f)
        b = f.valid_to or a + timedelta(days=10)
        if a <= hi and b >= lo:
            out.append(f)
    return out


def _same_product(a: Offer, b: Offer) -> bool:
    if similarity(a, b) < 0.8:
        return False
    qa, qb = quantity(a.description or ""), quantity(b.description or "")
    if qa and qb:
        return qa.kind == qb.kind          # formati diversi si confrontano al kg / al litro
    return True


def _price_in_format(prev: Offer, now: Offer) -> int | None:
    """Il prezzo di allora riportato al formato di adesso (stessa confezione, oppure prezzo al kg/litro)."""
    qa, qb = quantity(now.description or ""), quantity(prev.description or "")
    if (qa and qb and abs(qa.amount - qb.amount) <= 0.02 * max(qa.amount, qb.amount)) or (not qa and not qb):
        return prev.price_cents
    pa, pb = per_unit(now), per_unit(prev)
    if pa and pb and pa[1] == pb[1] and pa[0] > 0:
        return int(round(now.price_cents * pb[0] / pa[0]))
    return None


def check(session: Session, store: Store, flyer: Flyer, days: int = WINDOW_DAYS) -> list[Finding]:
    """Le offerte di questo volantino con un prezzo barrato più alto del minimo dei 30 giorni prima."""
    prev = previous_flyers(session, store, flyer, days)
    if not prev:
        return []
    candidates = [(f, o) for f in prev for o in f.offers]
    out = []
    for o in flyer.offers:
        if not o.old_price_cents:
            continue
        best: tuple[int, Offer, Flyer] | None = None
        for f, p in candidates:
            if not _same_product(o, p):
                continue
            cents = _price_in_format(p, o)
            if cents is None:
                continue
            if best is None or cents < best[0]:
                best = (cents, p, f)
        if best is not None and best[0] < o.old_price_cents:
            out.append(Finding(offer=o, previous=best[1], previous_flyer=best[2], lowest_cents=best[0]))
    return out


def summary(session: Session, store: Store, flyer: Flyer) -> dict:
    prev = previous_flyers(session, store, flyer)
    findings = check(session, store, flyer)
    barred = sum(1 for o in flyer.offers if o.old_price_cents)
    return {"previous_flyers": len(prev), "barred": barred, "findings": [x.as_dict() for x in findings],
            "checked": bool(prev)}
