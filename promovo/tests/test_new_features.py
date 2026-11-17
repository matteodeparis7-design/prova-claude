"""Funzioni aggiunte: impostazioni negozio, logo, gestione offerte, panoramica agenzia, aggiornamento database."""
import io
import sqlite3

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from promovo.api import create_app
from promovo.db import Database
from promovo.models import Store

from conftest import FakeLLM
from test_api import live_pdf, make_store, register, upload  # noqa: F401  (fixture e utilità condivise)


@pytest.fixture
def client(tmp_settings):
    app = create_app(tmp_settings, llm=FakeLLM(), db=Database("sqlite://"))
    with TestClient(app) as c:
        yield c


def png(color=(200, 30, 30), bg=(255, 255, 255), fmt="PNG"):
    im = Image.new("RGB", (300, 200), bg)
    ImageDraw.Draw(im).ellipse((60, 30, 240, 170), fill=color)
    buf = io.BytesIO()
    im.save(buf, format=fmt)
    return buf.getvalue()


def test_store_settings_and_logo(client):
    h = register(client)
    s = make_store(client, h, tone="giovane", hashtags=["#Offerte", "offerte", "spesa smart"],
                   whatsapp="333 1112223", website="https://esempio.it", video_music=False)
    assert s["tone"] == "giovane" and s["hashtags"] == ["Offerte", "spesasmart"] and s["video_music"] is False
    assert client.post("/api/stores", headers=h, json={"name": "XY", "tone": "arrabbiato"}).status_code == 422
    assert s["logo_url"] is None
    r = client.post(f"/api/stores/{s['id']}/logo", headers=h, files={"file": ("logo.jpg", png(fmt="JPEG"), "image/jpeg")})
    assert r.status_code == 200 and r.json()["logo_url"]
    logo = client.get(r.json()["logo_url"], headers=h)
    im = Image.open(io.BytesIO(logo.content))
    assert im.mode == "RGBA" and im.getchannel("A").getextrema()[0] == 0   # sfondo bianco tolto
    assert client.post(f"/api/stores/{s['id']}/logo", headers=h, files={"file": ("x.png", b"rotto", "image/png")}).status_code == 400
    assert client.delete(f"/api/stores/{s['id']}/logo", headers=h).status_code == 204
    assert client.get(f"/api/stores/{s['id']}", headers=h).json()["logo_url"] is None


def test_offer_management(client, live_pdf):  # noqa: F811
    h = register(client)
    s = make_store(client, h)
    f = upload(client, h, s["id"], live_pdf)
    first = f["offers"][0]
    assert first["photo_url"] and client.get(first["photo_url"], headers=h).status_code == 200

    # Uno sconto stampato non viene cancellato modificando un altro campo.
    client.patch(f"/api/offers/{first['id']}", headers=h, json={"conditions": "con carta"})
    assert client.get(f"/api/flyers/{f['id']}", headers=h).json()["offers"][0]["discount_percent"] == first["discount_percent"]

    # Aggiunta manuale
    r = client.post(f"/api/flyers/{f['id']}/offers", headers=h,
                    json={"name": "Pandoro", "price": "4,99", "old_price": "6,90", "category": "dolci e snack"})
    assert r.status_code == 201 and r.json()["manual"] and r.json()["price_verified"] and r.json()["discount_percent"] == 28
    assert client.post(f"/api/flyers/{f['id']}/offers", headers=h, json={"name": "X", "price": "0"}).status_code == 422
    assert client.post(f"/api/flyers/{f['id']}/offers", headers=h,
                       json={"name": "X", "price": "2,00", "old_price": "1,00"}).status_code == 422
    manual_id = r.json()["id"]
    up = client.post(f"/api/offers/{manual_id}/photo", headers=h, files={"file": ("p.png", png(), "image/png")})
    assert up.status_code == 200 and up.json()["photo_url"]
    assert client.post(f"/api/offers/{manual_id}/photo", headers=h, files={"file": ("p.png", b"", "image/png")}).status_code == 400

    # Eliminazione
    assert client.delete(f"/api/offers/{manual_id}", headers=h).status_code == 204
    assert len(client.get(f"/api/flyers/{f['id']}", headers=h).json()["offers"]) == 12


def test_confirm_prices(client, live_pdf):  # noqa: F811
    h = register(client)
    s = make_store(client, h)
    f = upload(client, h, s["id"], live_pdf)
    ids = [o["id"] for o in f["offers"]]
    # Simula prezzi non verificati (come in un volantino fatto di immagini).
    for i in ids[:3]:
        client.patch(f"/api/offers/{i}", headers=h, json={"confirm": False})
    from promovo.models import Offer
    app_db = client.app.state.promovo.db
    with app_db.session() as ses:
        for o in ses.query(Offer).filter(Offer.id.in_(ids[:3])):
            o.price_verified, o.verified_by = False, ""
    assert client.get(f"/api/flyers/{f['id']}", headers=h).json()["unverified_count"] == 3
    r = client.patch(f"/api/offers/{ids[0]}", headers=h, json={"confirm": True})
    assert r.json()["price_verified"] and r.json()["verified_by"] == "persona"
    r = client.post(f"/api/flyers/{f['id']}/confirm", headers=h, json={"offer_ids": ids})
    assert r.json() == {"confirmed": 2, "unverified_left": 0}


def test_agency_overview(client, live_pdf):  # noqa: F811
    h = register(client)
    a = make_store(client, h, name="Negozio A")
    make_store(client, h, name="Negozio B")
    upload(client, h, a["id"], live_pdf)
    ov = client.get("/api/agency/overview", headers=h).json()
    assert [x["store"]["name"] for x in ov] == ["Negozio A", "Negozio B"]
    assert ov[0]["last_flyer"]["offer_count"] == 12 and ov[1]["last_flyer"] is None
    other = register(client, "altro@test.it", "Altra")
    assert client.get("/api/agency/overview", headers=other).json() == []


def test_old_database_is_upgraded(tmp_path):
    path = tmp_path / "vecchio.db"
    con = sqlite3.connect(path)
    con.executescript("""
    CREATE TABLE organizations (id INTEGER PRIMARY KEY, name VARCHAR(200), kind VARCHAR(20), created_at DATETIME);
    CREATE TABLE stores (id INTEGER PRIMARY KEY, organization_id INTEGER, name VARCHAR(200), banner VARCHAR(200),
      address VARCHAR(300), city VARCHAR(120), phone VARCHAR(40), opening_hours JSON, brand_color VARCHAR(7),
      accent_color VARCHAR(7), services JSON, pickup_enabled BOOLEAN, created_at DATETIME);
    INSERT INTO organizations VALUES (1, 'Vecchia', 'agency', '2026-01-01');
    INSERT INTO stores VALUES (1, 1, 'Negozio vecchio', '', '', '', '', '{}', '#D7262E', '#FFD23F', '[]', 1, '2026-01-01');
    """)
    con.commit()
    con.close()
    db = Database(f"sqlite:///{path}")
    db.create_all()
    assert db.upgrade_columns() == []          # già aggiornato
    with db.session() as s:
        st = s.get(Store, 1)
        assert st.name == "Negozio vecchio" and st.tone == "familiare" and st.hashtags == [] and st.video_music is True
