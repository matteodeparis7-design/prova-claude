"""Offerte attive di un negozio, usate dall'assistente clienti e dalla fedeltà."""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Flyer, FlyerStatus, Offer
from ..text_utils import normalize, similarity


def active_flyers(session: Session, store_id: int, today: date | None = None) -> list[Flyer]:
    """Volantini validi oggi; se nessuno ha date, l'ultimo pronto."""
    today = today or date.today()
    ready = session.scalars(
        select(Flyer).where(Flyer.store_id == store_id, Flyer.status == FlyerStatus.ready)
        .order_by(Flyer.created_at.desc(), Flyer.id.desc())
    ).all()
    current = [f for f in ready if f.valid_from and f.valid_to and f.valid_from <= today <= f.valid_to]
    if current:
        return current
    undated = [f for f in ready if not (f.valid_from and f.valid_to)]
    return undated[:1]


def active_offers(session: Session, store_id: int, today: date | None = None) -> list[Offer]:
    offers: list[Offer] = []
    for f in active_flyers(session, store_id, today):
        offers.extend(f.offers)
    return offers


def search_offers(offers: list[Offer], query: str = "", category: str = "", limit: int = 15) -> list[Offer]:
    q = normalize(query)
    pool = [o for o in offers if not category or o.category == category]
    if not q:
        return sorted(pool, key=lambda o: (not o.is_featured, -(o.discount_percent or 0)))[:limit]
    scored = []
    for o in pool:
        hay = f"{o.brand} {o.name} {o.description} {o.category}"
        nh = normalize(hay)
        score = 1.0 if q in nh else max(similarity(q, o.name), max(
            (similarity(w, t) for w in q.split() for t in nh.split()), default=0.0))
        if score >= 0.72:
            scored.append((score, o))
    scored.sort(key=lambda t: -t[0])
    return [o for _, o in scored[:limit]]
