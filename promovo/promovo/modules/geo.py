"""Dove si trova il negozio (e il comune di un produttore), per la Filiera vicina e il meteo.

Fonte gratuita e senza chiave: Nominatim (OpenStreetMap), al massimo una richiesta al secondo come chiede la sua
politica d'uso, con un nome di programma generico. Dati © OpenStreetMap contributors (licenza ODbL): Promovo
scrive l'attribuzione dove mostra i risultati.
"""
from __future__ import annotations

import json
import math
import re
import threading
import time
import unicodedata
import urllib.parse
import urllib.request
from typing import Callable

from ..models import Store

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "Promovo/1.0 (programma per la comunicazione dei negozi)"
ATTRIBUTION = "Dati della mappa © OpenStreetMap contributors (ODbL)"


class GeoUnavailable(RuntimeError):
    pass


Fetch = Callable[[str, dict], dict]


_nominatim_last = [0.0]


def nominatim_turn() -> None:
    """Regola di Nominatim: al massimo una richiesta al secondo per tutto il programma (mappa e meteo)."""
    with _lock:
        wait = _nominatim_last[0] + 1.1 - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _nominatim_last[0] = time.monotonic()


def http_json(url: str, params: dict, timeout: float = 20.0) -> dict:
    full = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(full, headers={"User-Agent": USER_AGENT, "Accept-Language": "it"})
    tries = 2 if url == NOMINATIM_URL else 1     # Nominatim: un secondo tentativo se l'errore è momentaneo
    for attempt in range(tries):
        if url == NOMINATIM_URL:
            nominatim_turn()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (URL fissi, solo https)
                return json.loads(r.read().decode("utf-8"))
        except Exception as exc:
            if attempt + 1 >= tries:
                raise GeoUnavailable(f"mappa non raggiungibile ({exc.__class__.__name__})") from exc
            time.sleep(2)
    raise GeoUnavailable("mappa non raggiungibile")


_cache: dict[tuple, tuple[float, object]] = {}
_lock = threading.Lock()


def _cached(key: tuple, ttl: float, fn):
    now = time.monotonic()
    with _lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < ttl:
            return hit[1]
    value = fn()
    with _lock:
        _cache[key] = (now, value)
    return value


def _norm(s: str) -> str:
    s = "".join(c for c in unicodedata.normalize("NFD", (s or "").lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def city_center(city: str, fetch: Fetch = http_json) -> tuple[float, float, str] | None:
    """Centro del comune (non della provincia): ricerca strutturata per città, poi ricerca libera."""
    for params in ({"city": city, "country": "Italia"}, {"q": f"{city}, Italia"}):
        res = fetch(NOMINATIM_URL, {**params, "format": "jsonv2", "limit": 1, "countrycodes": "it"})
        if isinstance(res, list) and res:
            return float(res[0]["lat"]), float(res[0]["lon"]), res[0].get("name") or city
    return None


def locate(store: Store, fetch: Fetch = http_json) -> tuple[float, float, str]:
    """Coordinate del negozio: dall'indirizzo, se è davvero in quel comune; altrimenti dal centro del comune."""
    city = (store.city or "").strip()
    address = (store.address or "").strip()
    if not city and not address:
        raise GeoUnavailable("indica la città del negozio (pagina Negozio)")

    def go():
        center = city_center(city or address, fetch)
        if center is None:
            raise GeoUnavailable(f"non trovo «{city or address}» sulla mappa: controlla la città nella pagina Negozio")
        if address and city:
            want = _norm(city)
            for params in ({"street": address, "city": city, "country": "Italia"}, {"q": f"{address}, {city}, Italia"}):
                try:
                    res = fetch(NOMINATIM_URL, {**params, "format": "jsonv2", "limit": 3, "countrycodes": "it",
                                                "addressdetails": 1})
                except GeoUnavailable:
                    res = None
                for r in res if isinstance(res, list) else []:
                    a = r.get("address") or {}
                    towns = {_norm(a.get(k, "")) for k in ("city", "town", "village", "municipality", "hamlet")} - {""}
                    lat_, lon_ = float(r["lat"]), float(r["lon"])
                    # una via con lo stesso nome in un altro comune non va bene
                    same_town = want in towns if towns else distance_m(center[0], center[1], lat_, lon_) < 8000
                    if same_town and distance_m(center[0], center[1], lat_, lon_) < 25000:
                        return lat_, lon_, "indirizzo"
        return center[0], center[1], "città"
    return _cached(("loc", _norm(address), _norm(city)), 30 * 86400, go)
