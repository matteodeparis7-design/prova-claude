"""Salvaspreco: offerte lampo dalle scadenze, regole di vendita, cibo salvato."""
from __future__ import annotations

import io
from datetime import date, timedelta

import pymupdf
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from promovo.api import create_app
from promovo.db import Database
from promovo.models import Organization, Store
from promovo.modules import rescue as rs

from conftest import FakeLLM, make_store, register, upload

TODAY = date(2026, 11, 19)


def test_rules_discount_and_price():
    # scaduto («da consumarsi entro» passato): non si vende
    with pytest.raises(rs.RescueError, match="tolto"):
        rs.check_sellable("scadenza", TODAY - timedelta(days=1), TODAY)
    # termine minimo passato: si vende, con la nota per il negozio
    assert "trasparenza" in rs.check_sellable("tmc", TODAY - timedelta(days=5), TODAY)[0]
    assert "Scade oggi" in rs.check_sellable("scadenza", TODAY, TODAY)[0]
    with pytest.raises(rs.RescueError):
        rs.check_sellable("scadenza", None, TODAY)
    # più vicina la data, più forte lo sconto
    s = [rs.suggest_discount("scadenza", "scadenza", TODAY + timedelta(days=d), TODAY) for d in (0, 1, 2, 4, 9)]
    assert s == [50, 40, 30, 25, 20]
    assert rs.suggest_discount("forno", "", None, TODAY) == 50
    # prezzo «da cartellino», mai sopra lo sconto scelto e mai uguale al prezzo pieno
    assert rs.rescue_price(219, 40) == 129
    assert rs.rescue_price(169, 40) == 99
    assert rs.rescue_price(129, 50) == 59
    assert rs.rescue_price(5, 50) < 5
    assert rs.unit_weight_g("Yogurt", "4 x 125 g") == 500
    assert rs.unit_weight_g("Latte", "1 litro") == 1000
    assert rs.unit_weight_g("Banane", "") is None


def test_create_texts_close_and_month(tmp_path):
    db = Database("sqlite://")
    db.create_all()
    with db.session() as s:
        org = Organization(name="Org")
        s.add(org)
        s.flush()
        st = Store(organization_id=org.id, name="Market Esempio", address="Via Roma 1", city="Colleferro",
                   tone="familiare", hashtags=["colleferro"])
        s.add(st)
        s.flush()
        y, notes = rs.create(s, st, rs.RescueIn(name="Yogurt alla fragola", description="4 x 125 g",
                                               date_kind="scadenza", expires_on=TODAY + timedelta(days=1), qty=12,
                                               price_cents=219), tmp_path, TODAY)
        assert notes == [] and y.rescue_price_cents == 129 and y.unit_weight_g == 500
        assert y.until == TODAY + timedelta(days=1)            # dura fino alla data di scadenza
        assert "Da consumarsi entro il 20/11" in y.text and "#salvaspreco" in y.text and "#colleferro" in y.text
        assert "€ 1,29" in y.text and "€ 2,19" in y.text and "-41%" in y.text and "12 pezzi" in y.text
        assert "SALVASPRECO" in y.short_text and len(y.short_text) < 300
        for p in (y.story_path, y.post_path):
            assert Image.open(p).size in ((1080, 1920), (1080, 1350))
        # un prodotto con foto (anche del telefono) e uno al kg
        photo = Image.new("RGB", (800, 600), (200, 160, 60))
        b, _ = rs.create(s, st, rs.RescueIn(name="Banane", reason="maturo", qty=6, unit="kg", price_cents=169),
                         tmp_path, TODAY, photo=photo)
        assert b.photo_path and b.until == TODAY and "al kg" in b.text and "spremute" in b.text
        # non si inventano qualità: niente «buono», «fresco», «delizioso»
        for t in (y.text, b.text):
            assert not any(w in t.lower() for w in ("buono", "fresco", "delizios", "squisit"))
        with pytest.raises(rs.RescueError, match="non possono essere di più"):
            rs.close(y, 13)
        rs.close(y, 10)
        rs.close(b, 5.5)
        st_ = rs.month_stats(s, st, 2026, 11)
        assert st_["products"] == 2 and st_["closed"] == 2
        assert st_["kg_saved"] == 10.5                          # 10 confezioni da 500 g + 5,5 kg di banane
        assert st_["revenue_cents"] == 10 * 129 + int(round(5.5 * 99))
        assert st_["sell_through"] == round(15.5 * 100 / 18)
        num, label = rs.impact_headline(st_)
        assert num == "10 kg" and "spreco" in label
        assert rs.impact_image(st, st_).size == (1080, 1350)
        assert "abbiamo salvato 10 kg" in rs.impact_text(st, st_)
        pdf = rs.tags_pdf(st, [y, b], tmp_path / "t.pdf", TODAY)
        assert pymupdf.open(pdf).page_count == 1


def test_validation_errors(tmp_path):
    db = Database("sqlite://")
    db.create_all()
    with db.session() as s:
        org = Organization(name="Org")
        s.add(org)
        s.flush()
        st = Store(organization_id=org.id, name="N")
        s.add(st)
        s.flush()
        bad = [rs.RescueIn(name="", price_cents=100), rs.RescueIn(name="Pane", price_cents=0),
               rs.RescueIn(name="Pane", price_cents=100, rescue_price_cents=120),
               rs.RescueIn(name="Pane", price_cents=100, qty=0),
               rs.RescueIn(name="Latte", price_cents=100, date_kind="scadenza", expires_on=TODAY + timedelta(days=1),
                           until=TODAY + timedelta(days=3))]
        for d in bad:
            with pytest.raises(rs.RescueError):
                rs.create(s, st, d, tmp_path, TODAY)


def test_api_flow(tmp_settings, live_pdf):
    app = create_app(tmp_settings, llm=FakeLLM(), db=Database("sqlite://"))
    today = date.today()
    with TestClient(app) as c:
        h = register(c)
        s = make_store(c, h)
        f = upload(c, h, s["id"], live_pdf)
        sug = c.get(f"/api/stores/{s['id']}/rescues/suggest", headers=h,
                    params={"price": "2,19", "date_kind": "scadenza", "expires_on": (today + timedelta(days=1)).isoformat(),
                            "name": "Yogurt", "description": "4 x 125 g"}).json()
        assert sug["ok"] and sug["pct"] == 40 and sug["price"] == "€ 1,29" and sug["weight_g"] == 500
        bad = c.get(f"/api/stores/{s['id']}/rescues/suggest", headers=h,
                    params={"date_kind": "scadenza", "expires_on": (today - timedelta(days=1)).isoformat()}).json()
        assert bad["ok"] is False and "tolto" in bad["error"]
        # dal volantino: nome, formato, prezzo e foto arrivano da soli
        o = f["offers"][0] if "offers" in f else c.get(f"/api/flyers/{f['id']}", headers=h).json()["offers"][0]
        r = c.post(f"/api/stores/{s['id']}/rescues", headers=h,
                   data={"offer_id": str(o["id"]), "reason": "confezione", "qty": "3"})
        assert r.status_code == 201, r.text
        a = r.json()
        assert a["name"] == o["name"] and a["price_cents"] == o["price_cents"] and a["discount_percent"] >= 25
        # scritto a mano, con una foto dal telefono
        buf = io.BytesIO()
        Image.new("RGB", (640, 480), (120, 180, 90)).save(buf, "JPEG")
        r = c.post(f"/api/stores/{s['id']}/rescues", headers=h,
                   data={"name": "Pane casereccio", "reason": "forno", "qty": "2,5", "unit": "kg", "price": "3,20"},
                   files={"photo": ("pane.jpg", buf.getvalue(), "image/jpeg")})
        assert r.status_code == 201, r.text
        b = r.json()
        assert b["rescue_price"] == "€ 1,59" and b["photo_url"] and b["qty_text"] == "2,5 kg"
        assert c.get(b["story_url"], headers=h).headers["content-type"] == "image/jpeg"
        # scaduto: rifiutato con il motivo
        r = c.post(f"/api/stores/{s['id']}/rescues", headers=h,
                   data={"name": "Latte", "price": "1,29", "date_kind": "scadenza",
                         "expires_on": (today - timedelta(days=2)).isoformat()})
        assert r.status_code == 400 and "tolto" in r.json()["detail"]
        # cartellini di quelli aperti
        pdf = c.get(f"/api/stores/{s['id']}/rescues-print", headers=h)
        assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
        # l'immagine del mese serve solo dopo aver segnato i venduti
        assert c.get(f"/api/stores/{s['id']}/rescues-impact.jpg", headers=h).status_code == 404
        assert c.post(f"/api/rescues/{b['id']}/close", headers=h, json={"sold": "9"}).status_code == 400
        done = c.post(f"/api/rescues/{b['id']}/close", headers=h, json={"sold": "2"}).json()
        assert done["closed"] and done["kg_saved"] == 2
        lst = c.get(f"/api/stores/{s['id']}/rescues", headers=h).json()
        assert len(lst["items"]) == 2 and lst["stats"]["kg_saved"] == 2 and "abbiamo salvato" in lst["impact_text"]
        img = c.get(f"/api/stores/{s['id']}/rescues-impact.jpg", headers=h)
        assert img.status_code == 200 and Image.open(io.BytesIO(img.content)).size == (1080, 1350)
        # il report della settimana racconta anche il Salvaspreco del mese del volantino
        if (f.get("valid_from") or today.isoformat())[:7] == today.isoformat()[:7]:
            rep = c.get(f"/api/flyers/{f['id']}/report.pdf", headers=h)
            text = "".join(pg.get_text() for pg in pymupdf.open(stream=rep.content, filetype="pdf"))
            assert "Salvaspreco di" in text and "kg di cibo salvato" in text
        # un altro account non vede niente
        h2 = register(c, email="altro@test.it", org="Altra")
        assert c.get(f"/api/rescues/{a['id']}/post", headers=h2).status_code == 404
        assert c.delete(f"/api/rescues/{a['id']}", headers=h).status_code == 204
        assert len(c.get(f"/api/stores/{s['id']}/rescues", headers=h).json()["items"]) == 1
