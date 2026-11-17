"""Dati dimostrativi: un account, un negozio e un volantino di prova valido da oggi."""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select

from .config import Settings
from .db import Database
from .models import Customer, Organization, Role, Store, User
from .modules.flyer.service import ingest_flyer
from .sample_flyer import build_sample_flyer
from .security import hash_password

DEMO_EMAIL = "demo@promovo.it"
DEMO_PASSWORD = "promovo2026"


def seed_demo(db: Database, settings: Settings) -> bool:
    """Crea i dati dimostrativi se non esistono già. Restituisce True se li ha creati."""
    with db.session() as s:
        if s.scalar(select(User).where(User.email == DEMO_EMAIL)):
            return False
        org = Organization(name="Agenzia Demo", kind="agency")
        s.add(org)
        s.flush()
        s.add(User(organization_id=org.id, email=DEMO_EMAIL, name="Demo", role=Role.owner,
                   password_hash=hash_password(DEMO_PASSWORD)))
        store = Store(organization_id=org.id, name="Supermercato Demo", banner="Demo", address="Via Roma 1",
                      city="Colleferro", phone="06 0000000", opening_hours={"lun-sab": "8:00-20:00", "dom": "9:00-13:00"},
                      services=["ritiro in negozio"])
        s.add(store)
        s.flush()
        start, end = date.today() - timedelta(days=1), date.today() + timedelta(days=10)
        pdf = build_sample_flyer(validity=f"Offerte valide dal {start:%d/%m/%Y} al {end:%d/%m/%Y}",
                                 banner="SUPERMERCATO DEMO")
        ingest_flyer(s, store, pdf, settings, None, title="Volantino di prova")
        s.add_all([
            Customer(store_id=store.id, name="Anna Verdi", phone="+393330000001", marketing_consent=True,
                     preferred_categories=["pesce"]),
            Customer(store_id=store.id, name="Bruno Neri", phone="+393330000002"),
        ])
    return True
