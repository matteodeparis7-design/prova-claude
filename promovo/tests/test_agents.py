"""Pilota automatico (gli agenti fanno tutto da soli) e chiavi facoltative dalla pagina Impostazioni."""
import dataclasses
import json

import anthropic
import httpx
import pytest
from fastapi.testclient import TestClient

from promovo.api import create_app
from promovo.db import Database

from conftest import make_store, register


@pytest.fixture
def client(tmp_settings):
    app = create_app(dataclasses.replace(tmp_settings, ai_mode="claude"), db=Database("sqlite://"))
    with TestClient(app) as c:
        yield c


class FakeMessages:
    def __init__(self, error=None):
        self.error, self.calls = error, 0

    def create(self, **kw):
        self.calls += 1
        if self.error:
            raise self.error
        return object()


class FakeAnthropic:
    def __init__(self, error=None):
        self.messages = FakeMessages(error)


def _error(cls, status, text="errore"):
    resp = httpx.Response(status, request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))
    return cls(text, response=resp, body=None)


def test_agents_work_without_any_key(client):
    h = register(client)
    assert client.get("/api/health").json()["ai"] is False
    st = client.get("/api/settings", headers=h).json()
    assert st["ai"] == {"configured": False, "masked": "", "source": "", "active": False}
    assert st["voice"]["configured"] is False


def test_ai_key_is_tested_saved_and_activated_live(client, tmp_settings):
    h = register(client)
    state = client.app.state.promovo
    bad = client.post("/api/settings/keys", headers=h, json={"service": "ai", "key": "ciao"})
    assert bad.status_code == 422 and "sk-ant-" in bad.json()["detail"]

    state.key_test_client = FakeAnthropic(_error(anthropic.AuthenticationError, 401))
    r = client.post("/api/settings/keys", headers=h, json={"service": "ai", "key": "sk-ant-api03-" + "x" * 40})
    assert r.status_code == 422 and "non valida" in r.json()["detail"]

    state.key_test_client = FakeAnthropic(_error(anthropic.BadRequestError, 400, "Your credit balance is too low"))
    r = client.post("/api/settings/keys", headers=h, json={"service": "ai", "key": "sk-ant-api03-" + "x" * 40})
    assert r.status_code == 422 and "credito" in r.json()["detail"]

    state.key_test_client, state.llm_client = FakeAnthropic(), FakeAnthropic()
    key = "sk-ant-api03-" + "y" * 40 + "WXYZ"
    r = client.post("/api/settings/keys", headers=h, json={"service": "ai", "key": f"  {key}\n"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ai"]["configured"] and body["ai"]["active"] and body["ai"]["source"] == "impostazioni"
    assert body["ai"]["masked"].endswith("WXYZ") and key not in json.dumps(body)        # mai la chiave intera
    assert client.get("/api/health").json()["ai"] is True                                  # attiva senza riavvio
    saved = json.loads((state.settings.data_dir / "chiavi.json").read_text())
    assert saved["ai"] == key

    r = client.delete("/api/settings/keys/ai", headers=h)
    assert r.json()["ai"]["configured"] is False and client.get("/api/health").json()["ai"] is False
    assert not (state.settings.data_dir / "chiavi.json").exists()


def test_only_the_owner_manages_keys(client):
    h = register(client)
    client.post("/api/users", headers=h, json={"email": "staff@negozio.it", "password": "password123", "role": "staff"})
    t = client.post("/api/auth/login", json={"email": "staff@negozio.it", "password": "password123"}).json()["token"]
    hs = {"Authorization": f"Bearer {t}"}
    assert client.get("/api/settings", headers=hs).status_code == 200
    assert client.post("/api/settings/keys", headers=hs, json={"service": "ai", "key": "sk-ant-" + "z" * 30}).status_code == 403


def test_autopilot_reads_and_makes_everything(client, live_pdf, monkeypatch):
    monkeypatch.setattr("promovo.api.app.AUTOPILOT_ITEMS", ["texts", "images"])
    h = register(client)
    store = make_store(client, h)
    r = client.post(f"/api/stores/{store['id']}/flyers", headers=h, files={"file": ("v.pdf", live_pdf, "application/pdf")},
                    data={"autopilot": "true"})
    assert r.status_code == 202 and r.json()["autopilot_job"]
    job = client.get(f"/api/jobs/{r.json()['autopilot_job']}", headers=h).json()
    assert job["status"] == "done", job
    assert job["result"]["stage"] == "done" and job["result"]["offers"] == 12 and job["result"]["unverified"] == 0
    assert job["result"]["done"] == ["texts", "images"] and job["result"]["errors"] == []
    kinds = {c["kind"] for c in client.get(f"/api/flyers/{r.json()['id']}/content", headers=h).json()}
    assert kinds == {"instagram", "facebook", "reel", "plan", "image"}


def test_autopilot_reports_unreadable_flyer(client, monkeypatch):
    import pymupdf
    doc = pymupdf.open()
    doc.new_page().insert_text((50, 100), "Buone feste da tutto lo staff", fontsize=20)
    h = register(client)
    store = make_store(client, h)
    r = client.post(f"/api/stores/{store['id']}/flyers", headers=h,
                    files={"file": ("v.pdf", doc.tobytes(), "application/pdf")}, data={"autopilot": "true"})
    job = client.get(f"/api/jobs/{r.json()['autopilot_job']}", headers=h).json()
    assert job["status"] == "failed" and "Nessuna offerta" in job["error"]


def test_chain_replicates_flyer_to_other_stores(client, live_pdf, monkeypatch):
    monkeypatch.setattr("promovo.api.app.AUTOPILOT_ITEMS", ["texts"])
    h = register(client)
    main = make_store(client, h)
    other = make_store(client, h, name="Superstore Velletri", address="Corso Italia 4", city="Velletri")
    third = make_store(client, h, name="Superstore Artena", address="Piazza Vittorio 2", city="Artena")
    r = client.post(f"/api/stores/{main['id']}/flyers", headers=h, files={"file": ("v.pdf", live_pdf, "application/pdf")})
    fid = r.json()["id"]
    r = client.post(f"/api/flyers/{fid}/replicate", headers=h, json={"store_ids": [other["id"], third["id"], main["id"]]})
    assert r.status_code == 202, r.text
    items = r.json()
    assert [i["store_id"] for i in items] == [other["id"], third["id"]]          # il negozio di partenza si salta
    for item, st in zip(items, (other, third)):
        job = client.get(f"/api/jobs/{item['job_id']}", headers=h).json()
        assert job["status"] == "done", job
        fl = client.get(f"/api/flyers/{item['flyer_id']}", headers=h).json()
        assert fl["store_id"] == st["id"] and len(fl["offers"]) == 12 and fl["unverified_count"] == 0
        ig = next(c for c in client.get(f"/api/flyers/{item['flyer_id']}/content", headers=h).json() if c["kind"] == "instagram")
        assert st["city"] in ig["body"]                                            # i dati sono del suo negozio
        img = client.get(fl["offers"][0]["image_url"], headers=h)
        assert img.status_code == 200
    # eliminare l'originale non tocca le copie
    assert client.delete(f"/api/flyers/{fid}", headers=h).status_code == 204
    fl = client.get(f"/api/flyers/{items[0]['flyer_id']}", headers=h).json()
    assert client.get(fl["offers"][0]["image_url"], headers=h).status_code == 200
    # un negozio di un'altra organizzazione non si può usare
    h2 = register(client, email="altro@test.it", org="Altra")
    foreign = make_store(client, h2, name="Altro negozio")
    r2 = client.post(f"/api/stores/{other['id']}/flyers", headers=h, files={"file": ("v.pdf", live_pdf, "application/pdf")})
    assert client.post(f"/api/flyers/{r2.json()['id']}/replicate", headers=h, json={"store_ids": [foreign["id"]]}).status_code == 404
