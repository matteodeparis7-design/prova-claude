"""Avvisi di servizio: festività, chiusure e orari, pronti per ogni canale e per tutti i punti vendita."""
from __future__ import annotations

import io
from datetime import date, timedelta

import pymupdf
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from promovo.api import create_app
from promovo.db import Database
from promovo.models import Notice, Store
from promovo.modules import notices as nt

from conftest import FakeLLM, make_store, register


def test_holidays_and_upcoming():
    h = dict((d, n) for d, n in nt.holidays(2027))
    assert h[date(2027, 3, 28)] == "Pasqua" and h[date(2027, 3, 29)].startswith("Lunedì dell'Angelo")
    assert h[date(2027, 10, 4)] == "San Francesco d'Assisi"          # festa nazionale dal 2026 (L. 151/2025)
    assert date(2025, 10, 4) not in dict(nt.holidays(2025))
    up = nt.upcoming(date(2026, 11, 20))
    assert [u["name"] for u in up][:3] == ["Immacolata Concezione", "Vigilia di Natale", "Natale"]
    assert up[0]["label"] == "martedì 8 dicembre"


def test_validation_and_texts():
    today = date(2026, 11, 20)
    with pytest.raises(nt.NoticeError, match="orari"):
        nt.validate(nt.NoticeIn("festivo", "Orari dell'Immacolata", date(2026, 12, 8), date(2026, 12, 8)), today)
    with pytest.raises(nt.NoticeError, match="passati"):
        nt.validate(nt.NoticeIn("chiusura", "Chiusura", date(2026, 11, 1), date(2026, 11, 2), closed=True), today)
    st = Store(name="Market Esempio", address="Via Roma 1", city="Colleferro", tone="familiare")
    n = Notice(kind="festivo", title="Orari di Natale", date_from=date(2026, 12, 24), date_to=date(2026, 12, 26),
               hours="", closed=True, message="")
    t = nt.texts(st, n)
    assert "Da giovedì 24 a sabato 26 dicembre: il negozio resta chiuso." in t["post"]
    assert "24/12/2026: chiuso" in t["google"] and "26/12/2026: chiuso" in t["google"]
    n2 = Notice(kind="festivo", title="Orari dell'Immacolata", date_from=date(2026, 12, 8), date_to=date(2026, 12, 8),
                hours="8:00 – 13:00", closed=False, message="Il banco del pesce resta chiuso.")
    t2 = nt.texts(st, n2)
    assert "Martedì 8 dicembre: aperti 8:00 – 13:00." in t2["post"] and "banco del pesce" in t2["status"]


def test_api_and_chain(tmp_settings):
    app = create_app(tmp_settings, llm=FakeLLM(), db=Database("sqlite://"))
    d = (date.today() + timedelta(days=10)).isoformat()
    with TestClient(app) as c:
        h = register(c)
        s1 = make_store(c, h)
        s2 = make_store(c, h, name="Superstore Segni", city="Segni")
        lst = c.get(f"/api/stores/{s1['id']}/notices", headers=h).json()
        assert lst["upcoming"] and lst["stores_in_org"] == 2
        bad = c.post(f"/api/stores/{s1['id']}/notices", headers=h, json={"kind": "festivo", "title": "Orari", "date_from": d})
        assert bad.status_code == 400
        r = c.post(f"/api/stores/{s1['id']}/notices", headers=h,
                   json={"kind": "festivo", "title": "Orari della festa", "date_from": d, "hours": "8:00 – 13:00",
                         "all_stores": True})
        assert r.status_code == 201, r.text
        n = r.json()
        assert n["created_for"] == 2 and "aperti 8:00 – 13:00" in n["post"]
        assert len(c.get(f"/api/stores/{s2['id']}/notices", headers=h).json()["items"]) == 1    # anche nell'altro negozio
        for url, size in ((n["image_url"], (1080, 1350)), (n["story_url"], (1080, 1920)), (n["screen_url"], (1920, 1080))):
            img = c.get(url, headers=h)
            assert img.status_code == 200 and Image.open(io.BytesIO(img.content)).size == size
        pdf = c.get(n["poster_url"], headers=h)
        assert pdf.status_code == 200 and round(pymupdf.open(stream=pdf.content, filetype="pdf")[0].rect.width) == 595
        h2 = register(c, email="altro@test.it", org="Altra")
        assert c.get(n["image_url"], headers=h2).status_code == 404
        assert c.delete(f"/api/notices/{n['id']}", headers=h).status_code == 204
