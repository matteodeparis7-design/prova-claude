"""Posizione del negozio e dei comuni (OpenStreetMap) per la Filiera vicina e il meteo; niente dati dei concorrenti."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from promovo.api import create_app
from promovo.db import Database
from promovo.models import Flyer, Store
from promovo.modules import geo

from conftest import FakeLLM, make_store, register


def test_address_in_another_town_falls_back_to_the_town_center():
    """«Via Roma 3» esiste in molti comuni: se la mappa trova quella di un altro paese si usa il centro del comune."""
    geo._cache.clear()

    def fetch(url, params):
        if "street" in params or (params.get("q", "").startswith("Via Roma")):
            return [{"lat": "41.60", "lon": "13.30"}]               # 25 km più in là: un altro comune
        return [{"lat": "41.806", "lon": "13.058", "name": "Paliano"}]
    lat, lon, how = geo.locate(Store(name="X", address="Via Roma 3", city="Paliano"), fetch)
    assert (round(lat, 3), round(lon, 3), how) == (41.806, 13.058, "città")


def test_no_competitor_features_and_old_competitor_flyers_are_deleted(tmp_settings, live_pdf):
    db = Database("sqlite://")
    app = create_app(tmp_settings, llm=FakeLLM(), db=db)
    with TestClient(app) as c:
        h = register(c)
        s = make_store(c, h)
        for path in (f"/api/stores/{s['id']}/competitors", f"/api/stores/{s['id']}/nearby"):
            assert c.get(path, headers=h).status_code in (404, 405)
        # un volantino di concorrente rimasto da una versione vecchia
        with db.session() as session:
            session.add(Flyer(store_id=s["id"], title="Volantino altrui", competitor="Altro negozio",
                              pdf_path=str(tmp_settings.data_dir / "vecchio.pdf"), pdf_sha256="x" * 64, page_count=1))
    create_app(tmp_settings, llm=FakeLLM(), db=db)              # il riavvio lo cancella
    with db.session() as session:
        assert session.scalars(select(Flyer).where(Flyer.competitor != "")).all() == []
