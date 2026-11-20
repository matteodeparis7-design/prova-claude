"""«Lavora con noi»: l'annuncio di lavoro rispetta le regole ed è pronto per ogni canale."""
from __future__ import annotations

import io

import pymupdf
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from promovo.api import create_app
from promovo.db import Database
from promovo.models import JobPost, Store
from promovo.modules import jobs

from conftest import FakeLLM, make_store, register


def _levels(d: jobs.JobIn) -> dict:
    out: dict = {}
    for i in jobs.check(d):
        out.setdefault(i.level, []).append(i.found.lower())
    return out


def test_check_blocks_discrimination():
    lv = _levels(jobs.JobIn(role="Commessa", requirements="Ragazza max 30 anni, bella presenza, nubile; "
                                                         "solo italiani; CV con foto; automunita", in_store=False))
    assert {"max 30 anni", "ragazza", "bella presenza", "nubile", "solo italian", ""} <= set(lv["err"])
    assert {"foto", "automunit", "commessa"} <= set(lv["warn"])
    assert lv["info"] == [""]                                       # retribuzione da indicare (dir. UE 2023/970)
    with pytest.raises(jobs.JobError, match="max 30 anni"):
        jobs.validate(jobs.JobIn(role="Cassiere", requirements="max 30 anni"))
    # frasi lecite che non devono essere bloccate
    ok = jobs.validate(jobs.JobIn(role="Addetto/a alle casse", requirements="Buona conoscenza dell'italiano; "
                                  "disponibilità ai turni nel fine settimana", offer="Formazione pagata",
                                  pay="Livello 5 CCNL Commercio"))
    assert not [i for i in ok.issues if i.level != "info"]
    with pytest.raises(jobs.JobError, match="https"):
        jobs.validate(jobs.JobIn(role="Magazziniere/a", apply_link="www.esempio.it"))


def test_texts_are_inclusive_and_complete():
    assert jobs.title_role("Cassiere") == "Cassiere (m/f)"
    assert jobs.title_role("Addetto/a al banco") == "Addetto/a al banco"
    st = Store(name="Market Esempio", address="Via Roma 1", city="Colleferro", tone="familiare")
    j = JobPost(role="Banconiere/a gastronomia", contract="determinato", hours="part-time", hours_note="24 ore",
                tasks="Servizio al banco", requirements="", offer="Formazione; sconto dipendenti", pay="",
                start="gennaio", apply_link="", apply_email="lavoro@esempio.it", in_store=True)
    t = jobs.texts(st, j)
    assert t["title"] == "Market Esempio – Colleferro cerca: Banconiere/a gastronomia"
    assert "Contratto: Tempo determinato, part-time (24 ore)" in t["full"]
    assert "• Manda il curriculum a lavoro@esempio.it" in t["full"]
    assert "Lascia il curriculum alla cassa (Via Roma 1, Colleferro)" in t["full"]
    assert jobs.LEGAL_NOTE in t["full"] and jobs.PRIVACY_NOTE in t["full"] and jobs.LEGAL_NOTE in t["post"]
    assert "#lavoroColleferro" in t["post"]


def test_api_and_chain(tmp_settings):
    app = create_app(tmp_settings, llm=FakeLLM(), db=Database("sqlite://"))
    body = {"role": "Addetto/a al banco gastronomia", "contract": "indeterminato", "hours": "full-time",
            "offer": "Contratto CCNL Commercio; formazione pagata", "pay": "Livello 4 CCNL Commercio",
            "apply_link": "https://esempio.it/lavora", "in_store": True}
    with TestClient(app) as c:
        h = register(c)
        s1 = make_store(c, h)
        s2 = make_store(c, h, name="Superstore Segni", city="Segni")
        chk = c.post("/api/job-posts/check", headers=h, json={**body, "requirements": "under 25"}).json()
        assert any(i["level"] == "err" and i["found"] == "under 25" for i in chk["issues"])
        bad = c.post(f"/api/stores/{s1['id']}/jobs", headers=h, json={**body, "requirements": "bella presenza"})
        assert bad.status_code == 400 and "bella presenza" in bad.json()["detail"]
        r = c.post(f"/api/stores/{s1['id']}/jobs", headers=h, json={**body, "all_stores": True})
        assert r.status_code == 201, r.text
        j = r.json()
        assert j["created_for"] == 2 and "cerca: Addetto/a al banco gastronomia" in j["post"]
        assert len(c.get(f"/api/stores/{s2['id']}/jobs", headers=h).json()["items"]) == 1
        for url, size in ((j["image_url"], (1080, 1350)), (j["story_url"], (1080, 1920)),
                          (j["screen_url"], (1920, 1080))):
            img = c.get(url, headers=h)
            assert img.status_code == 200 and Image.open(io.BytesIO(img.content)).size == size
        pdf = c.get(j["poster_url"], headers=h)
        assert pdf.status_code == 200 and round(pymupdf.open(stream=pdf.content, filetype="pdf")[0].rect.width) == 595
        h2 = register(c, email="altro@test.it", org="Altra")
        assert c.get(j["image_url"], headers=h2).status_code == 404
        assert c.delete(f"/api/job-posts/{j['id']}", headers=h).status_code == 204
        # il lavoro di Promovo (/api/jobs/{id}) non è toccato dalle nuove rotte
        assert c.get("/api/jobs/999999", headers=h).status_code == 404
