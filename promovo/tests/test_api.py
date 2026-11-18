from datetime import date, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from promovo.api import create_app
from promovo.db import Database
from promovo.modules.content.service import AIContent

from conftest import FakeLLM, make_store, register, upload


@pytest.fixture
def app_ctx(tmp_settings):
    llm = FakeLLM()
    app = create_app(tmp_settings, llm=llm, db=Database("sqlite://"))
    with TestClient(app) as client:
        yield client, llm


def test_health_and_dashboard(app_ctx):
    client, _ = app_ctx
    assert client.get("/api/health").json()["ok"] is True
    page = client.get("/")
    assert page.status_code == 200 and "PROMOVO" in page.text


def test_auth_flow(app_ctx):
    client, _ = app_ctx
    h = register(client)
    assert client.get("/api/me", headers=h).json()["role"] == "owner"
    assert client.post("/api/auth/register", json={"organization": "XY", "email": "TITOLARE@test.it",
                                                   "password": "password123"}).status_code == 409
    assert client.post("/api/auth/login", json={"email": "titolare@test.it", "password": "sbagliata1"}).status_code == 401
    tok = client.post("/api/auth/login", json={"email": "Titolare@Test.it", "password": "password123"}).json()["token"]
    h2 = {"Authorization": f"Bearer {tok}"}
    assert client.post("/api/auth/logout", headers=h2).status_code == 204
    assert client.get("/api/me", headers=h2).status_code == 401
    assert client.get("/api/me").status_code == 401
    assert client.post("/api/auth/register", json={"organization": "XY", "email": "nuovo@test.it",
                                                   "password": "corta"}).status_code == 422


def test_roles_and_isolation(app_ctx, live_pdf):
    client, _ = app_ctx
    owner = register(client)
    store = make_store(client, owner)
    r = client.post("/api/users", headers=owner, json={"email": "commesso@test.it", "password": "password123"})
    assert r.status_code == 201 and r.json()["role"] == "staff"
    staff = {"Authorization": "Bearer " + client.post("/api/auth/login", json={
        "email": "commesso@test.it", "password": "password123"}).json()["token"]}
    assert client.post("/api/stores", headers=staff, json={"name": "Altro"}).status_code == 403
    assert client.post("/api/users", headers=staff, json={"email": "x@test.it", "password": "password123"}).status_code == 403
    assert client.get(f"/api/stores/{store['id']}", headers=staff).status_code == 200

    flyer = upload(client, owner, store["id"], live_pdf)
    other = register(client, "altro@test.it", "Concorrente")
    for path in (f"/api/stores/{store['id']}", f"/api/flyers/{flyer['id']}",
                 f"/api/offers/{flyer['offers'][0]['id']}/image", f"/api/stores/{store['id']}/orders"):
        assert client.get(path, headers=other).status_code == 404, path
    assert client.get("/api/stores", headers=other).json() == []


def test_store_validation_and_patch(app_ctx):
    client, _ = app_ctx
    h = register(client)
    assert client.post("/api/stores", headers=h, json={"name": "X", "brand_color": "rosso"}).status_code == 422
    s = make_store(client, h)
    r = client.patch(f"/api/stores/{s['id']}", headers=h, json={"phone": "06 999", "brand_color": "#112233"})
    assert r.json()["phone"] == "06 999" and r.json()["brand_color"] == "#112233"
    assert client.delete(f"/api/stores/{s['id']}", headers=h).status_code == 204
    assert client.get(f"/api/stores/{s['id']}", headers=h).status_code == 404


def test_flyer_offers_content_video(app_ctx, live_pdf):
    client, llm = app_ctx
    h = register(client)
    store = make_store(client, h)
    flyer = upload(client, h, store["id"], live_pdf)
    assert flyer["status"] == "ready" and len(flyer["offers"]) == 12
    assert flyer["valid_from"] == (date.today() - timedelta(days=1)).isoformat()
    img = client.get(flyer["offers"][0]["image_url"], headers=h)
    assert img.status_code == 200 and img.content[:4] == b"\x89PNG"

    bad = client.post(f"/api/stores/{store['id']}/flyers", headers=h,
                      files={"file": ("x.pdf", b"non sono un pdf", "application/pdf")})
    assert bad.status_code == 400

    oid = flyer["offers"][0]["id"]
    assert client.patch(f"/api/offers/{oid}", headers=h, json={"price": "abc"}).status_code == 422
    assert client.patch(f"/api/offers/{oid}", headers=h, json={"price": "2,00", "old_price": "1,50"}).status_code == 422
    r = client.patch(f"/api/offers/{oid}", headers=h, json={"price": "0,69", "old_price": "1,29", "cost": "0,40"})
    o = r.json()
    assert o["price_cents"] == 69 and o["discount_percent"] == 47 and o["price_verified"] and o["cost_cents"] == 40
    assert client.patch(f"/api/offers/{oid}", headers=h, json={"category": "inventata"}).status_code == 422

    # Testi: l'IA finta risponde, il controllo prezzi agisce.
    llm.on_parse("AIContent", lambda c: AIContent(
        instagram_caption="Spaghetti a € 0,69.", hashtags=["offerte"], facebook_post="Tutto a € 0,01"))
    r = client.post(f"/api/flyers/{flyer['id']}/content", headers=h)
    assert r.status_code == 201
    body = r.json()
    assert body["source"] == "ai" and len(body["content"]) == 4 and body["warnings"]
    cid = body["content"][0]["id"]
    r = client.patch(f"/api/content/{cid}", headers=h, json={"approved": True, "body": "Testo corretto"})
    assert r.json()["approved"] and r.json()["body"] == "Testo corretto"

    # Video (piccolo, per velocità): lavoro in background, poi download.
    assert client.post(f"/api/flyers/{flyer['id']}/video?format=cinema", headers=h).status_code == 422
    job = client.post(f"/api/flyers/{flyer['id']}/video?format=portrait&scale=0.25", headers=h)
    assert job.status_code == 202
    j = client.get(f"/api/jobs/{job.json()['id']}", headers=h).json()
    assert j["status"] == "done", j
    assert j["result"]["offers"] == 6
    video = client.get(f"/api/content/{j['result']['content_id']}/file", headers=h)
    assert video.status_code == 200 and video.content[4:8] == b"ftyp"

    ov = client.get(f"/api/stores/{store['id']}/overview", headers=h).json()
    assert ov["flyers"] == 1 and ov["content_to_approve"] == 3  # due testi (uno è approvato) e il video

    # Rilettura: le offerte vengono ricreate da capo.
    r = client.post(f"/api/flyers/{flyer['id']}/reprocess", headers=h)
    assert r.status_code == 202
    again = client.get(f"/api/flyers/{flyer['id']}", headers=h).json()
    assert again["status"] == "ready" and len(again["offers"]) == 12
    assert again["offers"][0]["price_cents"] != 69  # la correzione manuale non sopravvive alla rilettura

    assert client.delete(f"/api/flyers/{flyer['id']}", headers=h).status_code == 204
    assert client.get(f"/api/flyers/{flyer['id']}", headers=h).status_code == 404


def test_video_job_failure_is_reported(app_ctx, live_pdf):
    client, _ = app_ctx
    h = register(client)
    store = make_store(client, h)
    flyer = upload(client, h, store["id"], live_pdf)
    with patch("promovo.api.app.render_flyer_video", side_effect=RuntimeError("disco pieno")):
        job = client.post(f"/api/flyers/{flyer['id']}/video", headers=h).json()
    j = client.get(f"/api/jobs/{job['id']}", headers=h).json()
    assert j["status"] == "failed" and "disco pieno" in j["error"]


