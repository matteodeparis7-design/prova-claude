"""Il meteo che vende: previsioni (finte, senza rete) -> consigli su cosa mettere in evidenza."""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from promovo.api import create_app
from promovo.db import Database
from promovo.models import Offer
from promovo.modules.content.service import generate_content
from promovo.modules.flyer.service import ingest_flyer
from promovo.modules.weather import service as w

from conftest import TODAY, FakeLLM, make_store, register, upload


def fake_fetch(days: list[tuple], calls: list | None = None):
    """Risposte come quelle di Open-Meteo. days: (data, max, min, mm, probabilità, codice)."""
    def fetch(url, params):
        if calls is not None:
            calls.append(url)
        if "geocoding" in url:
            return {"results": [{"latitude": 41.73, "longitude": 13.02, "name": params["name"]}]}
        return {"daily": {"time": [d[0].isoformat() for d in days], "temperature_2m_max": [d[1] for d in days],
                          "temperature_2m_min": [d[2] for d in days], "precipitation_sum": [d[3] for d in days],
                          "precipitation_probability_max": [d[4] for d in days], "weather_code": [d[5] for d in days]}}
    return fetch


@pytest.fixture(autouse=True)
def _clear_cache():
    w._cache.clear()
    yield
    w._cache.clear()


def _o(name, category="altro", desc=""):
    return Offer(name=name, category=category, description=desc, price_cents=100, page=1, position=0, bbox=[0, 0, 1, 1])


def test_signals_and_matching():
    hot = w.Day(date(2026, 7, 4), 33, 21, 0, 0, 0)
    cold = w.Day(date(2026, 1, 10), 7, 1, 0, 10, 3)
    wet = w.Day(date(2026, 1, 11), 12, 6, 8.5, 90, 63)
    assert hot.signals == ["caldo"] and cold.signals == ["freddo"] and wet.signals == ["pioggia"]
    assert hot.label == "Sabato 4 lug" and wet.sky == "pioggia"
    offers = [_o("Birra Peroni", "bevande"), _o("Gelato vaniglia", "dolci e snack"), _o("Minestrone surgelato"),
              _o("Lenticchie", "dispensa"), _o("Detersivo lavatrice", "igiene casa")]
    assert [o.name for o in w.matching_offers(offers, "caldo")] == ["Birra Peroni", "Gelato vaniglia"]
    assert [o.name for o in w.matching_offers(offers, "freddo")] == ["Minestrone surgelato", "Lenticchie"]
    assert "Detersivo lavatrice" not in [o.name for o in w.matching_offers(offers, "pioggia")]


def test_weekly_weather_for_flyer(session, store, sample_pdf, tmp_settings):
    flyer = ingest_flyer(session, store, sample_pdf, tmp_settings, None, today=TODAY)   # 13-22 novembre
    days = [(TODAY + timedelta(days=i), 30 if i == 6 else 18, 10, 6.0 if i == 4 else 0, 80 if i == 4 else 5,
             0 if i != 4 else 61) for i in range(7)]
    calls: list = []
    info = w.weekly_weather(store, flyer, fake_fetch(days, calls), today=TODAY)
    assert info["available"] and info["place"] == "Colleferro" and len(info["days"]) == 7
    sig = {a["signal"]: a for a in info["advice"]}
    assert set(sig) == {"caldo", "pioggia"}
    assert sig["caldo"]["label"] == "Sabato 21 nov"
    hot_names = {o["name"] for o in sig["caldo"]["offers"]}
    assert {"Acqua naturale", "Gelato vaniglia"} <= hot_names
    assert "Spaghetti di grano duro" in {o["name"] for o in sig["pioggia"]["offers"]}
    w.weekly_weather(store, flyer, fake_fetch(days, calls), today=TODAY)
    assert len(calls) == 2                                     # seconda volta dalla memoria: nessuna nuova richiesta
    # Il piano della settimana usa il meteo vero, il copywriter lo riceve come contesto.
    plan = generate_content(store, flyer, None, weather=info).texts["plan"]["body"]
    assert "Sabato 21 novembre, ore 11:00" in plan and "Previsto caldo, 30 °C" in plan
    assert "Previsto caldo" in w.weather_note(info) or "caldo" in w.weather_note(info)


def test_weather_never_blocks(store):
    def broken(url, params):
        raise w.WeatherUnavailable("previsioni non raggiungibili (URLError)")
    info = w.weekly_weather(store, None, broken)
    assert info == {"available": False, "reason": "previsioni non raggiungibili (URLError)", "days": [], "advice": []}
    store.city = ""
    assert "città" in w.weekly_weather(store, None, broken)["reason"]
    assert w.weekly_weather(store, None, broken, enabled=False)["reason"].startswith("meteo disattivato")
    assert w.weather_note(info) == ""


def test_api_weather(tmp_settings, live_pdf):
    import dataclasses
    app = create_app(dataclasses.replace(tmp_settings, weather=True), llm=FakeLLM(), db=Database("sqlite://"))
    today = date.today()
    days = [(today + timedelta(days=i), 31, 20, 0, 0, 0) for i in range(7)]
    app.state.promovo.weather_fetch = fake_fetch(days)
    with TestClient(app) as c:
        h = register(c)
        st = make_store(c, h)
        fl = upload(c, h, st["id"], live_pdf)
        r = c.get(f"/api/flyers/{fl['id']}/weather", headers=h)
        assert r.status_code == 200 and r.json()["available"]
        assert r.json()["advice"] and r.json()["advice"][0]["signal"] == "caldo"
        h2 = register(c, email="b@test.it", org="Altra")
        assert c.get(f"/api/flyers/{fl['id']}/weather", headers=h2).status_code == 404
