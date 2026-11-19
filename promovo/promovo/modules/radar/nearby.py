"""I supermercati veri intorno al negozio, per sapere quali volantini confrontare.

Fonti gratuite e senza chiave:
- posizione del negozio: Nominatim (OpenStreetMap) sull'indirizzo, oppure Open-Meteo sulla sola città;
- negozi della zona: Overpass (OpenStreetMap), cioè i supermercati e i minimarket segnati sulla mappa.
I dati © OpenStreetMap contributors (licenza ODbL): Promovo lo scrive sotto l'elenco.

Promovo non legge i prezzi dei concorrenti da siti di terzi: i prezzi arrivano solo dai volantini che
carichi tu (file, foto o link al PDF pubblicato dall'insegna). Così il confronto è vero e verificabile.
"""
from __future__ import annotations

import ipaddress
import json
import math
import re
import socket
import threading
import time
import unicodedata
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable

from ...models import Store

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
# Server pubblici della stessa mappa: se uno è fermo o non raggiungibile si prova il successivo.
OVERPASS_URLS = (OVERPASS_URL, "https://overpass.private.coffee/api/interpreter",
                 "https://overpass.kumi.systems/api/interpreter", "https://maps.mail.ru/osm/tools/overpass/api/interpreter")
USER_AGENT = "Promovo/1.0 (programma per la comunicazione dei negozi)"
ATTRIBUTION = "Dati della mappa © OpenStreetMap contributors (ODbL)"

KINDS = {"supermarket": "supermercato", "convenience": "minimarket", "department_store": "grande magazzino",
         "wholesale": "ingrosso", "greengrocer": "ortofrutta", "butcher": "macelleria"}


class NearbyUnavailable(RuntimeError):
    pass


Fetch = Callable[[str, dict], dict]


def http_json(url: str, params: dict, timeout: float = 25.0) -> dict:
    full = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(full, headers={"User-Agent": USER_AGENT, "Accept-Language": "it"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (URL fissi, solo https)
            return json.loads(r.read().decode("utf-8"))
    except Exception as exc:
        raise NearbyUnavailable(f"mappa non raggiungibile ({exc.__class__.__name__})") from exc


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


def locate(store: Store, fetch: Fetch = http_json) -> tuple[float, float, str]:
    """Coordinate del negozio: prima dall'indirizzo completo, altrimenti dal centro della città."""
    city = (store.city or "").strip()
    address = (store.address or "").strip()
    if not city and not address:
        raise NearbyUnavailable("indica la città del negozio (pagina Negozio)")

    def go():
        if address and city:
            try:
                res = fetch(NOMINATIM_URL, {"q": f"{address}, {city}, Italia", "format": "jsonv2", "limit": 1,
                                            "countrycodes": "it"})
                if isinstance(res, list) and res:
                    return float(res[0]["lat"]), float(res[0]["lon"]), "indirizzo"
            except NearbyUnavailable:
                pass
        data = fetch(GEO_URL, {"name": city or address, "count": 1, "language": "it", "countryCode": "IT"})
        hit = (data or {}).get("results") or []
        if not hit:
            raise NearbyUnavailable(f"non trovo «{city or address}» sulla mappa: controlla la città nella pagina Negozio")
        return float(hit[0]["latitude"]), float(hit[0]["longitude"]), "città"
    return _cached(("loc", _norm(address), _norm(city)), 30 * 86400, go)


@dataclass
class Place:
    name: str
    brand: str
    kind: str
    address: str
    distance_m: int
    lat: float
    lon: float
    website: str = ""

    def as_dict(self) -> dict:
        return {"name": self.name, "brand": self.brand, "kind": self.kind, "address": self.address,
                "distance_m": self.distance_m, "lat": self.lat, "lon": self.lon, "website": self.website,
                "label": self.label, "search": self.search_url}

    @property
    def label(self) -> str:
        base = self.brand or self.name
        street = self.address.split(",")[0] if self.address else ""
        return f"{base} {street}".strip() if street and street.lower() not in base.lower() else base

    @property
    def search_url(self) -> str:
        city = self.address.split(",")[-1].strip() if "," in self.address else ""
        q = f"volantino {self.brand or self.name} {city}".strip()
        return "https://www.google.com/search?" + urllib.parse.urlencode({"q": q})


def _is_self(store: Store, name: str, brand: str, dist: float) -> bool:
    if dist < 40:
        return True
    own = set(_norm(store.name).split()) - {"supermercato", "market", "il", "la", "di", "del"}
    theirs = set(_norm(f"{name} {brand}").split())
    return bool(own) and own <= theirs and dist < 150


def nearby(store: Store, radius_m: int = 3000, fetch: Fetch = http_json, limit: int = 30) -> dict:
    """Supermercati e minimarket entro il raggio, dal più vicino. Senza rete: NearbyUnavailable."""
    radius_m = max(500, min(int(radius_m), 15000))
    lat, lon, precision = locate(store, fetch)
    query = (f'[out:json][timeout:25];(nwr["shop"~"^(supermarket|convenience|department_store|wholesale)$"]'
             f'(around:{radius_m},{lat:.6f},{lon:.6f}););out center tags 200;')

    def go():
        last: Exception | None = None
        for url in OVERPASS_URLS:
            try:
                data = fetch(url, {"data": query})
                if isinstance(data, dict) and "elements" in data:
                    return data
            except NearbyUnavailable as exc:
                last = exc
        raise last or NearbyUnavailable("mappa non raggiungibile")
    data = _cached(("ovp", round(lat, 4), round(lon, 4), radius_m), 7 * 86400, go)
    places: dict[tuple, Place] = {}
    for el in (data or {}).get("elements", []):
        tags = el.get("tags") or {}
        name, brand = (tags.get("name") or "").strip(), (tags.get("brand") or "").strip()
        if not name and not brand:
            continue
        plat = el.get("lat") or (el.get("center") or {}).get("lat")
        plon = el.get("lon") or (el.get("center") or {}).get("lon")
        if plat is None or plon is None:
            continue
        dist = distance_m(lat, lon, float(plat), float(plon))
        if _is_self(store, name, brand, dist):
            continue
        street = " ".join(x for x in (tags.get("addr:street"), tags.get("addr:housenumber")) if x)
        town = tags.get("addr:city") or ""
        p = Place(name=name or brand, brand=brand, kind=KINDS.get(tags.get("shop", ""), "negozio"),
                  address=", ".join(x for x in (street, town) if x), distance_m=int(round(dist)),
                  lat=float(plat), lon=float(plon), website=tags.get("website") or tags.get("contact:website") or "")
        key = (_norm(p.name), round(p.lat, 3), round(p.lon, 3))
        if key not in places or places[key].distance_m > p.distance_m:
            places[key] = p
    out = sorted(places.values(), key=lambda p: (p.kind != "supermercato", p.distance_m))[:limit]
    out.sort(key=lambda p: p.distance_m)
    return {"center": {"lat": lat, "lon": lon, "precision": precision}, "radius_m": radius_m,
            "places": [p.as_dict() for p in out], "attribution": ATTRIBUTION}


# ---------------------------------------------------------------- volantino da un link

class LinkError(ValueError):
    pass


def _public_host(host: str) -> None:
    """Solo indirizzi pubblici: un link non deve poter raggiungere la rete di casa o del negozio."""
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError as exc:
        raise LinkError("Il sito del link non risponde: controlla l'indirizzo.") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise LinkError("Il link deve essere un indirizzo internet pubblico.")


def download_flyer(url: str, max_bytes: int, timeout: float = 30.0) -> bytes:
    """Scarica un volantino (PDF o immagine) da un link pubblico, come farebbe il browser."""
    url = (url or "").strip()
    u = urllib.parse.urlparse(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        raise LinkError("Incolla un link completo che inizia con https://")
    _public_host(u.hostname)

    class NoPrivateRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            nu = urllib.parse.urlparse(newurl)
            if nu.scheme not in ("http", "https") or not nu.hostname:
                raise LinkError("Il link porta a un indirizzo non valido.")
            _public_host(nu.hostname)
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    opener = urllib.request.build_opener(NoPrivateRedirect)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Promovo)", "Accept": "application/pdf,image/*,*/*"})
    try:
        with opener.open(req, timeout=timeout) as r:  # noqa: S310 (schema e host controllati sopra)
            data = r.read(max_bytes + 1)
            ctype = (r.headers.get("Content-Type") or "").lower()
    except LinkError:
        raise
    except Exception as exc:
        raise LinkError(f"Non riesco a scaricare il file ({exc.__class__.__name__}). Prova a scaricarlo e caricarlo a mano.") from exc
    if len(data) > max_bytes:
        raise LinkError(f"Il file supera {max_bytes // (1024 * 1024)} MB.")
    head = data[:16]
    is_file = head.startswith(b"%PDF") or head.startswith(b"\xff\xd8") or head.startswith(b"\x89PNG") or \
        (head.startswith(b"RIFF") and data[8:12] == b"WEBP")
    if not is_file:
        if "html" in ctype or data.lstrip()[:1] == b"<":
            raise LinkError("Il link apre una pagina web, non il volantino. Sul sito dell'insegna cerca «scarica PDF» "
                            "e incolla quel link, oppure salva il volantino e caricalo come file.")
        raise LinkError("Il link non porta a un PDF o a un'immagine.")
    return data
