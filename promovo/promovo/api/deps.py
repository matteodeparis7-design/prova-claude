"""Dipendenze condivise dalle rotte: sessione, utente autenticato, controllo accessi."""
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..config import Settings
from ..db import Database
from ..llm import LLM
from ..models import ContentPiece, Flyer, Job, Offer, Order, Role, Store, User
from ..security import user_for_token


@dataclass
class AppState:
    settings: Settings
    db: Database
    llm: LLM | None
    voice_client: object | None = None      # client HTTP per la voce (solo nei test se ne passa uno finto)


def state(request: Request) -> AppState:
    return request.app.state.promovo


def get_session(request: Request) -> Iterator[Session]:
    s = state(request).db.new_session()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def bearer_token(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


def current_user(request: Request, session: Session = Depends(get_session)) -> User:
    user = user_for_token(session, bearer_token(request))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Accesso richiesto.",
                            headers={"WWW-Authenticate": "Bearer"})
    return user


def require_owner(user: User = Depends(current_user)) -> User:
    if user.role != Role.owner:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Serve un account titolare.")
    return user


def _not_found(what: str) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, f"{what} non trovato.")


def store_for(session: Session, user: User, store_id: int) -> Store:
    store = session.get(Store, store_id)
    # Un negozio di un'altra organizzazione risulta "non trovato": non si rivela che esiste.
    if store is None or store.organization_id != user.organization_id:
        raise _not_found("Negozio")
    return store


def flyer_for(session: Session, user: User, flyer_id: int) -> Flyer:
    flyer = session.get(Flyer, flyer_id)
    if flyer is None or flyer.store.organization_id != user.organization_id:
        raise _not_found("Volantino")
    return flyer


def offer_for(session: Session, user: User, offer_id: int) -> Offer:
    offer = session.get(Offer, offer_id)
    if offer is None or offer.flyer.store.organization_id != user.organization_id:
        raise _not_found("Offerta")
    return offer


def content_for(session: Session, user: User, content_id: int) -> ContentPiece:
    piece = session.get(ContentPiece, content_id)
    if piece is None or session.get(Store, piece.store_id).organization_id != user.organization_id:
        raise _not_found("Contenuto")
    return piece


def order_for(session: Session, user: User, order_id: int) -> Order:
    order = session.get(Order, order_id)
    if order is None or session.get(Store, order.store_id).organization_id != user.organization_id:
        raise _not_found("Ordine")
    return order


def job_for(session: Session, user: User, job_id: int) -> Job:
    job = session.get(Job, job_id)
    if job is None or session.get(Store, job.store_id).organization_id != user.organization_id:
        raise _not_found("Lavoro")
    return job
