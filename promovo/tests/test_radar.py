"""Radar del quartiere: lettura dei volantini dei concorrenti e confronto onesto dei prezzi."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from promovo.api import create_app
from promovo.db import Database
from promovo.models import Offer
from promovo.modules.catalog import active_offers
from promovo.modules.flyer.service import create_flyer, process_flyer
from promovo.modules.radar.service import per_unit, quantity, radar, similarity, tokens
from promovo.sample_flyer import SampleProduct, build_sample_flyer

from conftest import TODAY, FakeLLM, make_store, register, upload

# Il "concorrente": stessi periodi, alcuni prezzi più alti, altri più bassi, formati diversi.
RIVAL = [
    SampleProduct("Spaghetti", "500 g", 89, None, (230, 190, 90)),                  # noi 0,79: meno cari
    SampleProduct("Passata di pomodoro", "700 g", 89, None, (200, 40, 40)),         # noi 0,99: più cari
    SampleProduct("Caffè macinato", "500 g", 449, None, (90, 60, 40)),              # 8,98/kg contro noi 9,96/kg
    SampleProduct("Mele Golden", "al kg", 149, None, (230, 210, 60)),               # uguale
    SampleProduct("Olio extravergine di oliva", "750 ml", 599, None, (120, 150, 40)),  # 7,99/l contro noi 6,99/l
    SampleProduct("Tonno all'olio di oliva", "3 x 80 g", 299, None, (150, 150, 160)),  # noi non lo abbiamo
]


@pytest.fixture(scope="module")
def rival_pdf() -> bytes:
    return build_sample_flyer(RIVAL, validity="Offerte valide dal 14 al 24 novembre 2026", banner="CONCORRENTE")


def _o(name, desc="", price=100, brand="", category="altro", unit=""):
    return Offer(name=name, description=desc, price_cents=price, brand=brand, category=category, unit_price_text=unit,
                 page=1, position=0, bbox=[0, 0, 1, 1])


def test_quantities_and_unit_prices():
    assert quantity("4 x 175 g").amount == 700
    assert (q := quantity("6 x 1,5 L")).amount == 9000 and q.kind == "volume"
    assert quantity("1 litro").amount == 1000 and quantity("30 lavaggi").kind == "lavaggi"
    assert quantity("assortiti") is None
    assert per_unit(_o("Mele", "al kg", 149)) == (149.0, "al kg")
    assert per_unit(_o("Caffè", "250 g", 249)) == (996.0, "al kg")
    assert per_unit(_o("Olio", "750 ml", 599))[1] == "al litro"
    assert per_unit(_o("Detersivo", "30 lavaggi", 399))[1] == "a lavaggio"
    assert per_unit(_o("Uovo di Pasqua", "", 999)) is None          # senza formato non si confronta


def test_name_matching():
    assert tokens("Mele Golden") == tokens("Mela golden")
    assert similarity(_o("Spaghetti di grano duro"), _o("Spaghetti")) > 0.62
    assert similarity(_o("Passata di pomodoro"), _o("Pomodori pelati")) < 0.62
    assert similarity(_o("Biscotti frollini", category="dolci e snack"),
                      _o("Biscotti frollini", category="igiene casa")) < similarity(_o("Biscotti frollini"),
                                                                                    _o("Biscotti frollini"))


def _ingest(session, store, pdf, settings, competitor=""):
    f = create_flyer(session, store, pdf, settings, competitor=competitor)
    return process_flyer(session, f, settings, None, today=TODAY)


def test_radar_report(session, store, sample_pdf, rival_pdf, tmp_settings):
    own = _ingest(session, store, sample_pdf, tmp_settings)
    rival = _ingest(session, store, rival_pdf, tmp_settings, competitor="Market Rivale")
    assert rival.competitor == "Market Rivale" and len(rival.offers) == 6
    rep = radar(session, store, own)
    by = {r["offer"]: r for r in rep["rows"]}
    assert by["Spaghetti di grano duro"]["verdict"] == "meno caro"
    assert by["Passata di pomodoro"]["verdict"] == "più caro"
    assert by["Caffè macinato"]["verdict"] == "più caro"            # confronto al kg: 9,96 contro 8,98
    assert by["Caffè macinato"]["own_unit"] == "€ 9,96 al kg"
    assert by["Mele Golden"]["verdict"] == "uguale"
    assert by["Olio extravergine di oliva"]["verdict"] == "meno caro"  # al litro: 6,99 contro 7,99
    assert "Tonno" not in " ".join(by)                                  # non lo vendiamo: nessun confronto inventato
    assert rep["summary"] == {"compared": 5, "cheaper": 2, "dearer": 2, "same": 1}
    ids = {o.name: o.id for o in own.offers}
    assert set(rep["suggest_feature"]) == {ids["Spaghetti di grano duro"], ids["Olio extravergine di oliva"]}
    # I volantini dei concorrenti non entrano mai nelle offerte del negozio (assistente, materiali).
    assert {o.flyer_id for o in active_offers(session, store.id, TODAY)} == {own.id}


@pytest.fixture
def client(tmp_settings):
    app = create_app(tmp_settings, llm=FakeLLM(), db=Database("sqlite://"))
    with TestClient(app) as c:
        yield c


def test_api_competitors_and_radar(client, live_pdf):
    from datetime import date, timedelta
    h = register(client)
    st = make_store(client, h)
    own = upload(client, h, st["id"], live_pdf)
    start, end = date.today(), date.today() + timedelta(days=8)
    rival = build_sample_flyer(RIVAL, validity=f"Offerte valide dal {start:%d/%m/%Y} al {end:%d/%m/%Y}")
    r = client.post(f"/api/stores/{st['id']}/competitors", headers=h, data={"competitor": "x"},
                    files={"file": ("r.pdf", rival, "application/pdf")})
    assert r.status_code == 400                                         # nome troppo corto
    r = client.post(f"/api/stores/{st['id']}/competitors", headers=h, data={"competitor": "Market Rivale"},
                    files={"file": ("r.pdf", rival, "application/pdf")})
    assert r.status_code == 202, r.text
    comps = client.get(f"/api/stores/{st['id']}/competitors", headers=h).json()
    assert len(comps) == 1 and comps[0]["competitor"] == "Market Rivale" and comps[0]["status"] == "ready"
    # la lista dei volantini del negozio non mostra quelli dei concorrenti
    assert [f["id"] for f in client.get(f"/api/stores/{st['id']}/flyers", headers=h).json()] == [own["id"]]
    rep = client.get(f"/api/flyers/{own['id']}/radar", headers=h).json()
    assert rep["summary"]["compared"] == 5 and rep["competitors"][0]["name"] == "Market Rivale"
    assert client.get(f"/api/flyers/{comps[0]['id']}/radar", headers=h).status_code == 400
    r = client.post(f"/api/flyers/{own['id']}/feature", headers=h, json={"offer_ids": rep["suggest_feature"]})
    assert r.status_code == 200
    feat = {o["id"] for o in r.json()["offers"] if o["is_featured"]}
    assert set(rep["suggest_feature"]) <= feat and rep["suggest_feature"]
    # un altro negozio non vede né il radar né i volantini dei concorrenti
    h2 = register(client, email="altro@test.it", org="Altra")
    assert client.get(f"/api/flyers/{own['id']}/radar", headers=h2).status_code == 404
    assert client.get(f"/api/stores/{st['id']}/competitors", headers=h2).status_code == 404
    assert client.delete(f"/api/flyers/{comps[0]['id']}", headers=h).status_code == 204
    assert client.get(f"/api/flyers/{own['id']}/radar", headers=h).json()["summary"]["compared"] == 0
