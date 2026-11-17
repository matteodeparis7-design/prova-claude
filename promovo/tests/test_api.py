from datetime import date, datetime, timedelta
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
        instagram_caption="Spaghetti a € 0,69!", hashtags=["offerte"], facebook_post="Offerte!",
        whatsapp_message="Offerte! Rispondi STOP per non ricevere più messaggi.",
        newsletter_subject="Novità", newsletter_body="Tutto a € 0,01"))
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
    assert ov["flyers"] == 1 and ov["content_to_approve"] == 4  # 3 testi + 1 video

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


def test_chat_orders_customers(app_ctx, live_pdf):
    client, llm = app_ctx
    h = register(client)
    store = make_store(client, h)
    flyer = upload(client, h, store["id"], live_pdf)
    llm.scripts.append([[("cerca_offerte", {"testo": "caffè", "categoria": ""})], "Il caffè è a € 2,49."])
    r = client.post(f"/api/stores/{store['id']}/chat", headers=h, json={"message": "Quanto costa il caffè?"})
    assert r.status_code == 200 and "2,49" in r.json()["reply"]
    conv = r.json()["conversation_id"]
    llm.scripts.append(["Prego!"])
    r = client.post(f"/public/stores/{store['id']}/chat", json={"message": "Grazie", "conversation_id": conv})
    assert r.json()["conversation_id"] == conv
    assert client.post(f"/public/stores/{store['id']}/chat", json={"message": "x", "conversation_id": 999}).status_code == 404
    assert client.post("/public/stores/999/chat", json={"message": "x"}).status_code == 404

    llm.unavailable = True
    assert client.post(f"/api/stores/{store['id']}/chat", headers=h, json={"message": "ciao"}).status_code == 503
    llm.unavailable = False

    # Ordine creato direttamente dallo strumento dell'assistente.
    pickup = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT18:00")
    oid = flyer["offers"][0]["id"]
    llm.scripts.append([[("crea_ordine_ritiro", {"nome": "Anna", "telefono": "3471112223",
                                                 "articoli": [{"offerta_id": oid, "quantita": 2}],
                                                 "ritiro": pickup, "note": ""})], "Fatto"])
    client.post(f"/api/stores/{store['id']}/chat", headers=h, json={"message": "confermo"})
    orders = client.get(f"/api/stores/{store['id']}/orders", headers=h).json()
    assert len(orders) == 1, "l'ordine doveva essere creato"
    order = orders[0]
    assert order["total_cents"] == 2 * flyer["offers"][0]["price_cents"]
    assert client.patch(f"/api/orders/{order['id']}", headers=h, json={"status": "collected"}).status_code == 409
    for st in ("confirmed", "ready", "collected"):
        assert client.patch(f"/api/orders/{order['id']}", headers=h, json={"status": st}).status_code == 200
    assert client.patch(f"/api/orders/{order['id']}", headers=h, json={"status": "cancelled"}).status_code == 409


def test_customers_campaign_sales(app_ctx, live_pdf):
    client, _ = app_ctx
    h = register(client)
    store = make_store(client, h)
    flyer = upload(client, h, store["id"], live_pdf)
    sid = store["id"]
    assert client.post(f"/api/stores/{sid}/customers", headers=h, json={"phone": "abc"}).status_code == 422
    assert client.post(f"/api/stores/{sid}/customers", headers=h,
                       json={"phone": "3330000001", "preferred_categories": ["boh"]}).status_code == 422
    c = client.post(f"/api/stores/{sid}/customers", headers=h,
                    json={"name": "Anna", "phone": "333 0000001", "marketing_consent": True}).json()
    assert c["phone"] == "+393330000001" and c["marketing_consent"]
    assert client.post(f"/api/stores/{sid}/customers", headers=h, json={"phone": "+39 333 0000001"}).status_code == 409
    client.post(f"/api/stores/{sid}/customers", headers=h, json={"name": "Bruno", "phone": "3330000002"})
    msgs = client.post(f"/api/flyers/{flyer['id']}/campaign", headers=h).json()["messages"]
    assert len(msgs) == 1
    assert client.post(f"/api/stores/{sid}/inbound", headers=h, json={"phone": "3330000001", "text": "STOP"}).json()["unsubscribed"]
    assert client.post(f"/api/flyers/{flyer['id']}/campaign", headers=h).json()["messages"] == []
    r = client.patch(f"/api/customers/{c['id']}/consent", headers=h, json={"marketing_consent": True})
    assert r.json()["marketing_consent"]

    before = date.today() - timedelta(days=5)
    during = date.today()
    csv_data = (f"data;prodotto;quantita;incasso\n{before:%d/%m/%Y};Spaghetti di grano duro;10;12,90\n"
                f"{during:%d/%m/%Y};Spaghetti di grano duro;25;19,75\n")
    r = client.post(f"/api/stores/{sid}/sales", headers=h, files={"file": ("v.csv", csv_data.encode(), "text/csv")})
    assert r.status_code == 201 and r.json()["imported"] == 2
    bad = client.post(f"/api/stores/{sid}/sales", headers=h, files={"file": ("v.csv", b"a,b\n1,2\n", "text/csv")})
    assert bad.status_code == 400
    perf = client.get(f"/api/flyers/{flyer['id']}/performance", headers=h).json()
    pasta = next(o for o in perf["offers"] if o["name"].startswith("Spaghetti"))
    assert pasta["uplift_percent"] == 150.0


def test_public_chat_rate_limit(app_ctx, live_pdf):
    client, llm = app_ctx
    h = register(client)
    store = make_store(client, h)
    llm.scripts.extend([["ok"]] * 25)
    codes = [client.post(f"/public/stores/{store['id']}/chat", json={"message": "ciao"}).status_code
             for _ in range(22)]
    assert codes.count(200) == 20 and codes[-1] == 429
