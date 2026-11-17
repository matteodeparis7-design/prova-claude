"""Agente "Fedeltà": offerte personalizzate per i clienti che hanno dato il consenso.

Regole di privacy: si scrive solo a chi ha marketing_consent=True; chi risponde
STOP viene escluso subito e per sempre (finché non ridà il consenso).
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models import ContentPiece, Customer, Flyer, Offer, Store
from ...money import format_eur
from ..assistant.agent import OrderError, normalize_phone
from ..content.service import featured_offers, validity_text

STOP_WORDS = {"stop", "basta", "cancellami", "disiscrivimi", "unsubscribe"}


def _ordered_categories(session: Session, customer: Customer) -> list[str]:
    counts: Counter[str] = Counter()
    for order in customer.orders:
        for item in order.items:
            if item.offer_id is None:
                continue
            offer = session.get(Offer, item.offer_id)
            if offer is not None:
                counts[offer.category] += item.quantity
    out = list(dict.fromkeys(customer.preferred_categories or []))
    for cat, _ in counts.most_common():
        if cat not in out:
            out.append(cat)
    return out


def pick_for_customer(session: Session, customer: Customer, flyer: Flyer, limit: int = 3) -> list[Offer]:
    cats = _ordered_categories(session, customer)
    chosen: list[Offer] = []
    for cat in cats:
        for o in sorted((o for o in flyer.offers if o.category == cat),
                        key=lambda o: (-(o.discount_percent or 0), o.price_cents)):
            if o not in chosen:
                chosen.append(o)
            if len(chosen) >= limit:
                return chosen
    for o in featured_offers(flyer, limit * 2):
        if o not in chosen:
            chosen.append(o)
        if len(chosen) >= limit:
            break
    return chosen


def personal_message(store: Store, flyer: Flyer, customer: Customer, offers: list[Offer]) -> str:
    first = customer.name.split()[0] if customer.name.strip() else ""
    greet = f"Ciao {first}!" if first else "Ciao!"
    when = validity_text(flyer)
    lines = "\n".join(f"• {o.name}{' ' + o.description if o.description else ''}: {format_eur(o.price_cents)}"
                      + (f" invece di {format_eur(o.old_price_cents)}" if o.old_price_cents else "")
                      for o in offers)
    return (f"{greet} Abbiamo scelto per te alcune offerte di {store.name}{' ' + when if when else ''}:\n"
            f"{lines}\n\nRispondi STOP per non ricevere più messaggi.")


def build_campaign(session: Session, store: Store, flyer: Flyer) -> list[ContentPiece]:
    """Prepara (senza inviare) un messaggio personale per ogni cliente con consenso."""
    customers = session.scalars(select(Customer).where(Customer.store_id == store.id,
                                                       Customer.marketing_consent.is_(True))).all()
    for old in session.scalars(select(ContentPiece).where(ContentPiece.flyer_id == flyer.id,
                                                          ContentPiece.kind == "whatsapp_personal")).all():
        session.delete(old)
    session.flush()
    pieces = []
    for c in customers:
        offers = pick_for_customer(session, c, flyer)
        if not offers:
            continue
        piece = ContentPiece(store_id=store.id, flyer_id=flyer.id, kind="whatsapp_personal",
                             title=f"Messaggio per {c.name or c.phone}",
                             body=personal_message(store, flyer, c, offers),
                             meta={"customer_id": c.id, "phone": c.phone, "offer_ids": [o.id for o in offers]})
        session.add(piece)
        pieces.append(piece)
    session.flush()
    return pieces


def set_consent(session: Session, customer: Customer, consent: bool) -> None:
    customer.marketing_consent = consent
    customer.consent_at = datetime.now(timezone.utc) if consent else None
    session.flush()


def handle_inbound(session: Session, store: Store, phone: str, text: str) -> bool:
    """True se il messaggio era una richiesta di cancellazione (e il consenso è stato tolto)."""
    if text.strip().lower().strip(".! ") not in STOP_WORDS:
        return False
    try:
        phone = normalize_phone(phone)
    except OrderError:
        return True
    c = session.scalar(select(Customer).where(Customer.store_id == store.id, Customer.phone == phone))
    if c is not None and c.marketing_consent:
        set_consent(session, c, False)
    return True
