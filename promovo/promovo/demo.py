"""Dati dimostrativi: un account, un negozio e un volantino di prova valido da oggi."""
from __future__ import annotations

import io
from datetime import date, timedelta

from PIL import Image, ImageDraw

from sqlalchemy import select

from .config import Settings
from .db import Database
from .imaging import load_logo
from .models import Customer, Organization, Role, Store, User
from .modules.flyer.service import ingest_flyer
from .modules.video.render import font
from .sample_flyer import SampleProduct, build_sample_flyer
from .security import hash_password

DEMO_EMAIL = "demo@promovo.it"
DEMO_PASSWORD = "promovo2026"


def demo_logo() -> bytes:
    """Logo del negozio dimostrativo: un marchio semplice, inventato."""
    img = Image.new("RGB", (720, 260), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((10, 30, 210, 230), radius=50, fill=(215, 38, 46))
    d.polygon([(60, 95), (160, 95), (145, 175), (75, 175)], fill=(255, 255, 255))
    d.arc((80, 55, 140, 115), 180, 360, fill=(255, 255, 255), width=12)
    d.text((240, 92), "Supermercato", font=font(56, True), fill=(20, 27, 45), anchor="lm")
    d.text((240, 165), "DEMO", font=font(64, True), fill=(215, 38, 46), anchor="lm")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


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
                      services=["ritiro in negozio"], tone="familiare", whatsapp="333 0000000",
                      hashtags=["supermercatodemo", "spesacolleferro"])
        s.add(store)
        s.flush()
        settings.ensure_dirs()
        store.logo_path = str(load_logo(demo_logo(), settings.data_dir / "logos" / f"{store.id}_demo.png"))
        start, end = date.today() - timedelta(days=1), date.today() + timedelta(days=10)
        pdf = build_sample_flyer(validity=f"Offerte valide dal {start:%d/%m/%Y} al {end:%d/%m/%Y}",
                                 banner="SUPERMERCATO DEMO", illustrated=True)
        ingest_flyer(s, store, pdf, settings, None, title="Volantino di prova")
        # Un concorrente immaginario, per vedere subito il radar del quartiere.
        rival = build_sample_flyer(
            [SampleProduct("Spaghetti", "500 g", 89, None, (230, 190, 90)),
             SampleProduct("Passata di pomodoro", "700 g", 89, None, (200, 40, 40)),
             SampleProduct("Caffè macinato", "500 g", 449, None, (90, 60, 40)),
             SampleProduct("Olio extravergine di oliva", "750 ml", 599, None, (120, 150, 40)),
             SampleProduct("Biscotti frollini", "350 g", 149, None, (210, 160, 90)),
             SampleProduct("Salmone affumicato", "100 g", 329, None, (240, 140, 100))],
            validity=f"Offerte valide dal {start:%d/%m/%Y} al {end:%d/%m/%Y}", banner="CONCORRENTE")
        from .modules.flyer.service import create_flyer, process_flyer
        process_flyer(s, create_flyer(s, store, rival, settings, title="Volantino Market Esempio",
                                      competitor="Market Esempio (concorrente di prova)"), settings, None)
        s.add_all([
            Customer(store_id=store.id, name="Anna Verdi", phone="+393330000001", marketing_consent=True,
                     preferred_categories=["pesce"]),
            Customer(store_id=store.id, name="Bruno Neri", phone="+393330000002"),
        ])
    return True
