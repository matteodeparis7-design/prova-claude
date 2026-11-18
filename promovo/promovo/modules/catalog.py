"""Offerte attive di un negozio (volantino in corso)."""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Flyer, FlyerStatus, Offer


def active_flyers(session: Session, store_id: int, today: date | None = None) -> list[Flyer]:
    """Volantini validi oggi; se nessuno ha date, l'ultimo pronto."""
    today = today or date.today()
    ready = session.scalars(
        select(Flyer).where(Flyer.store_id == store_id, Flyer.status == FlyerStatus.ready, Flyer.competitor == "")
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
