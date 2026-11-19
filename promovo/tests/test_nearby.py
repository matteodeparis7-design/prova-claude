"""Concorrenti veri nella zona (OpenStreetMap) e volantino del concorrente da un link."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from promovo.api import create_app
from promovo.db import Database
from promovo.models import Store
from promovo.modules.radar import nearby as nb

from conftest import FakeLLM, make_store, register

# Colleferro, via Roma: coordinate e negozi verosimili (nomi di fantasia nei test).
HERE = (41.7290, 13.0040)


def fake_map(calls=None, shops_search=False):
    def fetch(url, params):
        if calls is not None:
            calls.append(url)
        if url == nb.NOMINATIM_URL and "viewbox" in params:            # ricerca dei negozi con Nominatim
            if not shops_search:
                return []
            if params["q"] == "supermarket":
                return [{"lat": "41.7330", "lon": "13.0100", "category": "shop", "type": "supermarket", "name": "Market Uno",
                         "address": {"road": "Via Latina", "house_number": "12", "town": "Colleferro"}},
                        {"lat": "41.7300", "lon": "13.0050", "category": "amenity", "type": "parking", "name": "Parcheggio"}]
            return [{"lat": "41.7295", "lon": "13.0060", "category": "shop", "type": "convenience", "name": "Alimentari Bianchi",
                     "address": {"road": "Corso Turati", "town": "Colleferro"}}]
        if url == nb.NOMINATIM_URL:
            return [{"lat": str(HERE[0]), "lon": str(HERE[1])}]
        assert url == nb.OVERPASS_URL and "around:" in params["data"]   # il primo server risponde
        return {"elements": [
            {"type": "node", "lat": 41.7291, "lon": 13.0041, "tags": {"shop": "supermarket", "name": "Superstore Colleferro"}},
            {"type": "node", "lat": 41.7330, "lon": 13.0100, "tags": {"shop": "supermarket", "name": "Market Uno", "brand": "Market Uno",
                                                                      "addr:street": "Via Latina", "addr:housenumber": "12", "addr:city": "Colleferro"}},
            {"type": "way", "center": {"lat": 41.7200, "lon": 12.9900}, "tags": {"shop": "supermarket", "name": "Discount Due"}},
            {"type": "node", "lat": 41.7295, "lon": 13.0060, "tags": {"shop": "convenience", "name": "Alimentari Bianchi"}},
            {"type": "node", "lat": 41.7400, "lon": 13.0300, "tags": {"shop": "supermarket"}},          # senza nome: scartato
            {"type": "node", "lat": 41.7331, "lon": 13.0101, "tags": {"shop": "supermarket", "name": "Market Uno"}},  # doppione
        ]}
    return fetch


def test_nearby_finds_real_competitors_sorted():
    nb._cache.clear()
    store = Store(name="Superstore Colleferro", address="Via Roma 1", city="Colleferro")
    res = nb.nearby(store, 3000, fetch=fake_map())
    names = [p["name"] for p in res["places"]]
    assert names == ["Alimentari Bianchi", "Market Uno", "Discount Due"]          # il negozio stesso escluso
    assert res["places"][0]["kind"] == "minimarket" and res["places"][1]["kind"] == "supermercato"
    assert res["places"][1]["label"] == "Market Uno Via Latina 12"
    assert all(a <= b for a, b in zip([p["distance_m"] for p in res["places"]], [p["distance_m"] for p in res["places"]][1:]))
    assert 600 < res["places"][1]["distance_m"] < 800
    assert "google.com/search" in res["places"][1]["search"] and "volantino" in res["places"][1]["search"]
    assert res["center"]["precision"] == "indirizzo" and "OpenStreetMap" in res["attribution"]


def test_nearby_without_address_or_network():
    nb._cache.clear()
    with pytest.raises(nb.NearbyUnavailable, match="città"):
        nb.nearby(Store(name="X", address="", city=""), fetch=fake_map())

    def broken(url, params):
        raise nb.NearbyUnavailable("mappa non raggiungibile (URLError)")
    with pytest.raises(nb.NearbyUnavailable):
        nb.nearby(Store(name="X", address="Via Roma 1", city="Paperopoli"), fetch=broken)


def test_link_download_is_safe():
    for bad in ("ftp://x/y.pdf", "file:///etc/passwd", "notaurl", "http://127.0.0.1/v.pdf", "http://192.168.1.10/v.pdf",
                "http://localhost:8000/api"):
        with pytest.raises(nb.LinkError):
            nb.download_flyer(bad, 10_000_000)


def test_api_nearby_and_link(tmp_settings, live_pdf):
    nb._cache.clear()
    app = create_app(tmp_settings, llm=FakeLLM(), db=Database("sqlite://"))
    app.state.promovo.nearby_fetch = fake_map()
    got = {}

    def fake_download(url, max_bytes):
        got["url"] = url
        if "pagina" in url:
            raise nb.LinkError("Il link apre una pagina web, non il volantino.")
        return live_pdf
    app.state.promovo.link_download = fake_download
    with TestClient(app) as c:
        h = register(c)
        st = make_store(c, h)
        r = c.get(f"/api/stores/{st['id']}/nearby?radius=3000", headers=h).json()
        assert r["ok"] and [p["name"] for p in r["places"]][:2] == ["Alimentari Bianchi", "Market Uno"]
        r = c.post(f"/api/stores/{st['id']}/competitors/link", headers=h,
                   json={"url": "https://esempio.it/volantino.pdf", "competitor": "Market Uno Via Latina"})
        assert r.status_code == 202, r.text
        comps = c.get(f"/api/stores/{st['id']}/competitors", headers=h).json()
        assert comps[0]["competitor"] == "Market Uno Via Latina" and comps[0]["status"] == "ready" and comps[0]["offer_count"] > 0
        r = c.post(f"/api/stores/{st['id']}/competitors/link", headers=h,
                   json={"url": "https://esempio.it/pagina", "competitor": "Discount Due"})
        assert r.status_code == 400 and "pagina web" in r.json()["detail"]
        h2 = register(c, email="b@test.it", org="Altra")
        assert c.get(f"/api/stores/{st['id']}/nearby", headers=h2).status_code == 404
        app.state.promovo.nearby_fetch = lambda url, params: (_ for _ in ()).throw(nb.NearbyUnavailable("mappa non raggiungibile (URLError)"))
        nb._cache.clear()
        r = c.get(f"/api/stores/{st['id']}/nearby", headers=h).json()
        assert r["ok"] is False and "mappa" in r["reason"]


def test_nearby_falls_back_to_another_map_server():
    nb._cache.clear()
    tried = []
    base = fake_map()

    def flaky(url, params):
        tried.append(url)
        if url == nb.OVERPASS_URL:
            raise nb.NearbyUnavailable("mappa non raggiungibile (URLError)")
        if url in nb.OVERPASS_URLS:
            return base(nb.OVERPASS_URL, params)
        return base(url, params)
    res = nb.nearby(Store(name="Superstore Colleferro", address="Via Roma 1", city="Colleferro"), fetch=flaky)
    assert [p["name"] for p in res["places"]][0] == "Alimentari Bianchi"
    assert tried[-2:] == list(nb.OVERPASS_URLS[:2])


def test_nearby_keeps_the_last_list_when_the_map_is_busy(tmp_path):
    nb._cache.clear()
    store = Store(name="Superstore Colleferro", address="Via Roma 1", city="Colleferro")
    first = nb.nearby(store, fetch=fake_map(), cache_dir=tmp_path, pause=0)
    assert first["saved_at"] is None and list(tmp_path.glob("*.json"))
    nb._cache.clear()
    base = fake_map()

    def busy(url, params):
        if url in nb.OVERPASS_URLS:
            raise nb.NearbyUnavailable("mappa non raggiungibile (HTTPError)")
        return base(url, params)
    again = nb.nearby(store, fetch=busy, cache_dir=tmp_path, pause=0)
    assert [p["name"] for p in again["places"]] == [p["name"] for p in first["places"]] and again["saved_at"]
    nb._cache.clear()
    def all_down(url, params):
        if url in nb.OVERPASS_URLS or "viewbox" in params:
            raise nb.NearbyUnavailable("mappa non raggiungibile (HTTPError)")
        return base(url, params)
    with pytest.raises(nb.NearbyUnavailable):
        nb.nearby(store, fetch=all_down, cache_dir=tmp_path / "vuota", pause=0)


def test_nearby_uses_nominatim_first_and_overpass_only_if_needed():
    nb._cache.clear()
    base = fake_map(shops_search=True)

    def overpass_down(url, params):
        if url in nb.OVERPASS_URLS:
            raise nb.NearbyUnavailable("mappa non raggiungibile (HTTPError)")
        return base(url, params)
    res = nb.nearby(Store(name="Superstore Colleferro", address="Via Roma 1", city="Colleferro"), fetch=overpass_down, pause=0)
    assert [p["name"] for p in res["places"]] == ["Alimentari Bianchi", "Market Uno"]     # niente parcheggi
    assert res["places"][1]["label"] == "Market Uno Via Latina 12"


def test_nearby_prefers_the_fast_search():
    nb._cache.clear()
    calls = []
    res = nb.nearby(Store(name="X", address="Via Roma 1", city="Colleferro"), fetch=fake_map(calls, shops_search=True), pause=0)
    assert res["places"] and not any(u in nb.OVERPASS_URLS for u in calls)       # Overpass non serve


def test_address_in_another_town_falls_back_to_the_town_center():
    """«Via Roma 3» esiste in molti comuni: se la mappa trova quella di un altro paese si usa il centro del comune."""
    nb._cache.clear()

    def fetch(url, params):
        if "street" in params or (params.get("q", "").startswith("Via Roma")):
            return [{"lat": "41.60", "lon": "13.30"}]               # 25 km più in là: un altro comune
        return [{"lat": "41.806", "lon": "13.058", "name": "Paliano"}]
    lat, lon, how = nb.locate(Store(name="X", address="Via Roma 3", city="Paliano"), fetch)
    assert (round(lat, 3), round(lon, 3), how) == (41.806, 13.058, "città")
