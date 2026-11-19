"""Materiali per il negozio: cartellini da scaffale, locandina, piano nel calendario."""
from __future__ import annotations

import io
import zipfile

import pymupdf
from fastapi.testclient import TestClient

from promovo.api import create_app
from promovo.db import Database
from promovo.models import Offer
from promovo.modules import printables as pr
from promovo.modules.flyer.service import ingest_flyer

from conftest import TODAY, FakeLLM, make_store, register, upload


def _o(desc, price, unit=""):
    return Offer(name="Prova", description=desc, price_cents=price, unit_price_text=unit, page=1, position=0,
                 bbox=[0, 0, 1, 1])


def test_unit_price_line():
    assert pr.unit_price_line(_o("500 g", 79)) == "€ 1,58 al kg"
    assert pr.unit_price_line(_o("6 x 1,5 L", 189)) == "€ 0,21 al litro"
    assert pr.unit_price_line(_o("al kg", 799)) == "€ 7,99 al kg"
    assert pr.unit_price_line(_o("", 199, unit="€ 9,95 al kg")) == "€ 9,95 al kg"     # quello stampato vince
    assert pr.unit_price_line(_o("", 199)) == ""


def test_tags_poster_and_calendar(session, store, sample_pdf, tmp_settings, tmp_path):
    f = ingest_flyer(session, store, sample_pdf, tmp_settings, None, today=TODAY)
    tags = pr.shelf_tags_pdf(store, f, tmp_path / "c.pdf")
    doc = pymupdf.open(tags)
    assert doc.page_count == 2 and round(doc[0].rect.width) == 595          # 12 offerte, 8 per foglio A4
    pdf = pr.poster_pdf(store, f, tmp_path / "l.pdf", "A3")
    assert round(pymupdf.open(pdf)[0].rect.height) == 1191                  # A3
    ics = pr.plan_ics(store, [{"date": "2026-11-20", "time": "12:30", "where": "Instagram · Reel", "what": "Apre, la settimana"},
                              {"date": "2026-11-20", "time": "", "where": "Schermi", "what": "In loop"}])
    assert ics.startswith("BEGIN:VCALENDAR") and ics.count("BEGIN:VEVENT") == 2
    assert "DTSTART;TZID=Europe/Rome:20261120T123000" in ics and "Apre\\, la settimana" in ics
    assert "DTSTART;VALUE=DATE:20261120" in ics and ics.count("BEGIN:VALARM") == 1


def test_api_print_and_zip(tmp_settings, live_pdf):
    app = create_app(tmp_settings, llm=FakeLLM(), db=Database("sqlite://"))
    with TestClient(app) as c:
        h = register(c)
        s = make_store(c, h)
        f = upload(c, h, s["id"], live_pdf)
        assert c.get(f"/api/flyers/{f['id']}/print/calendario", headers=h).status_code == 404   # prima i testi
        r = c.get(f"/api/flyers/{f['id']}/print/cartellini", headers=h)
        assert r.status_code == 200 and r.content[:4] == b"%PDF"
        assert c.get(f"/api/flyers/{f['id']}/print/locandina?size=A3", headers=h).content[:4] == b"%PDF"
        assert c.get(f"/api/flyers/{f['id']}/print/boh", headers=h).status_code == 404
        c.post(f"/api/flyers/{f['id']}/content", headers=h)
        cal = c.get(f"/api/flyers/{f['id']}/print/calendario", headers=h)
        assert cal.status_code == 200 and "BEGIN:VEVENT" in cal.text
        z = zipfile.ZipFile(io.BytesIO(c.get(f"/api/flyers/{f['id']}/kit.zip", headers=h).content))
        names = z.namelist()
        assert any(n.endswith("Da stampare/Cartellini_scaffale_A4.pdf") for n in names)
        assert any(n.endswith("Da stampare/Locandina_vetrina_A4.pdf") for n in names)
        assert any(n.endswith("Piano_nel_calendario.ics") for n in names)
