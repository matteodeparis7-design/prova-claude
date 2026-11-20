"""Il meteo che vende: le previsioni della zona del negozio diventano consigli su cosa mettere in evidenza.

Fonti, gratuite anche per uso commerciale e senza chiave:
- previsioni: MET Norway (Istituto meteorologico norvegese, api.met.no, dati CC BY 4.0), copre tutta l'Italia;
- posizione della città: Nominatim (OpenStreetMap), una richiesta per città, poi ricordata per 30 giorni.
Se la rete non c'è, Promovo lo dice e va avanti senza: il meteo è un consiglio, mai un blocco.

Regole semplici e spiegabili (il negoziante deve capire perché):
- caldo (massima >= 28 °C): bevande, acqua, birra, gelati, angurie e meloni, insalate, mozzarelle;
- freddo (massima <= 10 °C): minestre, legumi, brodo, cioccolata, tè e tisane, castagne, polenta;
- pioggia (probabilità >= 60% o almeno 3 mm): la spesa "da casa": pasta, sughi, dolci, pizza surgelata.
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
import unicodedata
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Callable

from ...models import Flyer, Offer, Store

log = logging.getLogger("promovo.weather")

GEO_URL = "https://nominatim.openstreetmap.org/search"
FORECAST_URL = "https://api.met.no/weatherapi/locationforecast/2.0/complete"
# MET Norway e Nominatim chiedono che il programma si presenti (niente User-Agent generico).
USER_AGENT = "Promovo/1.0 (programma per la comunicazione dei negozi)"
ATTRIBUTION = "Previsioni: MET Norway (CC BY 4.0)"
ROME = None


def _rome():
    global ROME
    if ROME is None:
        from zoneinfo import ZoneInfo
        ROME = ZoneInfo("Europe/Rome")
    return ROME


# Simboli di MET Norway -> codici WMO (per usare le stesse parole semplici)
MET_SYMBOL = {"clearsky": 0, "fair": 1, "partlycloudy": 2, "cloudy": 3, "fog": 45, "lightrain": 61, "rain": 63,
              "heavyrain": 65, "lightrainshowers": 80, "rainshowers": 81, "heavyrainshowers": 82, "lightsleet": 66,
              "sleet": 66, "heavysleet": 67, "lightsleetshowers": 66, "sleetshowers": 66, "heavysleetshowers": 67,
              "lightsnow": 71, "snow": 73, "heavysnow": 75, "lightsnowshowers": 85, "snowshowers": 85,
              "heavysnowshowers": 86}
_GIORNI = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]
_MESI = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]

# Codici meteo WMO -> parola semplice
WMO = {0: "sereno", 1: "poco nuvoloso", 2: "nuvoloso", 3: "coperto", 45: "nebbia", 48: "nebbia", 51: "pioviggine",
       53: "pioviggine", 55: "pioviggine", 61: "pioggia", 63: "pioggia", 65: "pioggia forte", 66: "pioggia gelata",
       67: "pioggia gelata", 71: "neve", 73: "neve", 75: "neve forte", 77: "neve", 80: "rovesci", 81: "rovesci",
       82: "rovesci forti", 85: "neve", 86: "neve", 95: "temporale", 96: "temporale", 99: "temporale"}

# Parole del prodotto (o categorie) che il tempo spinge. Le parole vanno senza accenti.
RULES = {
    "caldo": {"cats": {"bevande"}, "words": ["acqua", "birra", "gelat", "ghiaccio", "anguria", "cocomer", "melon",
                                                "pesche", "albicocc", "insalat", "mozzarell", "bresaola", "prosciutt",
                                                "te freddo", "the freddo", "spritz", "frutta", "yogurt", "affettat"],
              "why": "fa caldo: si cercano cose fresche e da bere"},
    "freddo": {"cats": set(), "words": ["minestr", "zupp", "legum", "fagiol", "lentic", "ceci", "brodo", "cioccolat",
                                        "tisan", "camomill", "castagn", "polenta", "arance", "agrumi", "vellutat",
                                        "cotechino", "lenticchie", "carne per bollito"],
               "why": "fa freddo: piatti caldi e dispensa d'inverno"},
    "pioggia": {"cats": {"pasta e riso", "dolci e snack"}, "words": ["pasta", "sugo", "passata", "pizza", "biscott",
                                                                    "merend", "pop corn", "cioccolat", "torta"],
                "why": "piove: si sta a casa e si cucina"},
}


def _norm(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", (s or "").lower()) if unicodedata.category(c) != "Mn")


@dataclass
class Day:
    day: date
    tmax: float
    tmin: float
    rain_mm: float
    rain_prob: int
    code: int

    @property
    def signals(self) -> list[str]:
        out = []
        if self.tmax >= 28:
            out.append("caldo")
        elif self.tmax <= 10:
            out.append("freddo")
        if self.rain_prob >= 60 or self.rain_mm >= 3:
            out.append("pioggia")
        return out

    @property
    def label(self) -> str:
        return f"{_GIORNI[self.day.weekday()]} {self.day.day} {_MESI[self.day.month - 1]}"

    @property
    def sky(self) -> str:
        return WMO.get(self.code, "variabile")


@dataclass
class Advice:
    day: Day
    signal: str
    why: str
    offers: list[Offer] = field(default_factory=list)


class WeatherUnavailable(RuntimeError):
    pass


Fetch = Callable[[str, dict], dict]


def http_json(url: str, params: dict, timeout: float = 8.0) -> dict:
    if url == GEO_URL:              # regola di Nominatim: una richiesta al secondo, condivisa con la mappa
        from ..geo import nominatim_turn
        nominatim_turn()
    full = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(full, headers={"User-Agent": USER_AGENT, "Accept-Language": "it"})
    for attempt in (1, 2):      # un secondo tentativo: a volte il servizio risponde in ritardo
        try:
            with urllib.request.urlopen(req, timeout=timeout * attempt) as r:  # noqa: S310 (URL fissi, solo https)
                return json.loads(r.read().decode("utf-8"))
        except Exception as exc:  # rete assente, servizio fermo, risposta strana: si va avanti senza meteo
            if attempt == 2:
                raise WeatherUnavailable(f"previsioni non raggiungibili ({exc.__class__.__name__})") from exc


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


def geocode(city: str, fetch: Fetch = http_json) -> tuple[float, float, str]:
    city = (city or "").strip()
    if not city:
        raise WeatherUnavailable("manca la città del negozio")

    def go():
        for params in ({"city": city, "country": "Italia"}, {"q": f"{city}, Italia"}):   # il comune, non la provincia
            res = fetch(GEO_URL, {**params, "format": "jsonv2", "limit": 1, "countrycodes": "it"})
            if isinstance(res, list) and res:
                r = res[0]
                return float(r["lat"]), float(r["lon"]), (r.get("name") or city)
        raise WeatherUnavailable(f"città «{city}» non trovata: controlla il nome nella pagina Negozio")
    return _cached(("geo", city.lower()), 30 * 86400, go)


def _symbol_code(sym: str) -> int:
    base = (sym or "").split("_")[0]
    if "thunder" in base:
        return 95
    return MET_SYMBOL.get(base, 2)


def parse_met(data: dict) -> list[Day]:
    """Dalle previsioni orarie/sesorarie di MET Norway ai giorni (ora italiana): massima, minima, pioggia, cielo."""
    from datetime import datetime
    series = ((data or {}).get("properties") or {}).get("timeseries") or []
    if not series:
        raise WeatherUnavailable("nessuna previsione disponibile")
    tz = _rome()
    days: dict[date, dict] = {}
    parsed = []
    for e in series:
        try:
            t = datetime.fromisoformat(e["time"].replace("Z", "+00:00")).astimezone(tz)
        except (KeyError, ValueError):
            continue
        parsed.append((t, e.get("data") or {}))
    for i, (t, d) in enumerate(parsed):
        nxt = parsed[i + 1][0] if i + 1 < len(parsed) else None
        step = (nxt - t).total_seconds() / 3600 if nxt else 6
        g = days.setdefault(t.date(), {"temps": [], "rain": 0.0, "prob": 0, "sym": None, "sym_gap": 99, "n": 0})
        g["n"] += 1
        inst = ((d.get("instant") or {}).get("details") or {})
        if "air_temperature" in inst:
            g["temps"].append(float(inst["air_temperature"]))
        p1, p6 = d.get("next_1_hours") or {}, d.get("next_6_hours") or {}
        d6 = p6.get("details") or {}
        for k in ("air_temperature_max", "air_temperature_min"):
            if k in d6:
                g["temps"].append(float(d6[k]))
        period = p1 if step <= 1.5 and p1 else p6           # ogni ora conta una volta sola
        pd = period.get("details") or {}
        g["rain"] += float(pd.get("precipitation_amount") or 0)
        for per in (p1, p6):
            pr = (per.get("details") or {}).get("probability_of_precipitation")
            if pr is not None:
                g["prob"] = max(g["prob"], int(round(float(pr))))
        sym = ((p6 or p1).get("summary") or {}).get("symbol_code")
        if sym and abs(t.hour - 12) < g["sym_gap"]:
            g["sym"], g["sym_gap"] = sym, abs(t.hour - 12)
    out = []
    for day in sorted(days):
        g = days[day]
        if not g["temps"] or (g["n"] < 2 and day != min(days)):
            continue                                           # giornata troppo poco coperta (l'ultima)
        prob = g["prob"] or (80 if g["rain"] >= 3 else 50 if g["rain"] >= 1 else 0)
        out.append(Day(day, max(g["temps"]), min(g["temps"]), round(g["rain"], 1), prob, _symbol_code(g["sym"])))
    if not out:
        raise WeatherUnavailable("nessuna previsione disponibile")
    return out


def forecast(lat: float, lon: float, fetch: Fetch = http_json) -> list[Day]:
    def go():
        try:
            return parse_met(fetch(FORECAST_URL, {"lat": f"{lat:.3f}", "lon": f"{lon:.3f}"}))[:8]
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise WeatherUnavailable("risposta delle previsioni non valida") from exc
    return _cached(("fc", round(lat, 2), round(lon, 2), date.today().isoformat()), 3 * 3600, go)


def matching_offers(offers: list[Offer], signal: str) -> list[Offer]:
    rule = RULES[signal]
    out = []
    for o in offers:
        text = _norm(" ".join(x for x in (o.brand, o.name, o.description) if x))
        if o.category in rule["cats"] or any(re.search(r"\b" + re.escape(w), text) for w in rule["words"]):
            out.append(o)
    return out


def advice(days: list[Day], offers: list[Offer], start: date | None = None, end: date | None = None) -> list[Advice]:
    """Un consiglio per ogni giorno con un segnale, solo se c'è qualcosa nel volantino da spingere."""
    out = []
    for d in days:
        if (start and d.day < start) or (end and d.day > end):
            continue
        for sig in d.signals:
            ms = matching_offers(offers, sig)
            if ms:
                out.append(Advice(day=d, signal=sig, why=RULES[sig]["why"], offers=ms[:5]))
    return out


def weekly_weather(store: Store, flyer: Flyer | None, fetch: Fetch | None = None, today: date | None = None,
                   enabled: bool = True) -> dict:
    """Previsioni e consigli per il volantino: pronto per l'interfaccia e per il copywriter."""
    if not enabled:
        return {"available": False, "reason": "meteo disattivato nelle impostazioni", "days": [], "advice": []}
    fetch = fetch or http_json
    try:
        lat, lon, place = geocode(store.city, fetch)
        days = forecast(lat, lon, fetch)
    except WeatherUnavailable as exc:
        return {"available": False, "reason": str(exc), "days": [], "advice": []}
    today = today or date.today()
    start = max(today, flyer.valid_from) if flyer is not None and flyer.valid_from else today
    end = flyer.valid_to if flyer is not None and flyer.valid_to else today + timedelta(days=6)
    from ..content.writer import available
    offers = available(flyer) if flyer is not None else []
    adv = advice(days, offers, start, end)
    return {
        "available": True, "place": place, "source": ATTRIBUTION,
        "days": [{"date": d.day.isoformat(), "label": d.label, "tmax": round(d.tmax), "tmin": round(d.tmin),
                  "rain_prob": d.rain_prob, "rain_mm": round(d.rain_mm, 1), "sky": d.sky, "signals": d.signals}
                 for d in days if start <= d.day <= end],
        "advice": [{"date": a.day.day.isoformat(), "label": a.day.label, "signal": a.signal, "why": a.why,
                    "tmax": round(a.day.tmax),
                    "offers": [{"id": o.id, "name": o.name, "is_featured": o.is_featured} for o in a.offers]}
                   for a in adv],
    }


def weather_note(info: dict) -> str:
    """Una riga di contesto vero per il copywriter (vuota se non c'è niente di rilevante)."""
    if not info.get("available"):
        return ""
    parts = []
    for a in info["advice"][:3]:
        word = {"caldo": f"caldo ({a['tmax']} °C)", "freddo": f"freddo ({a['tmax']} °C di massima)",
                "pioggia": "pioggia"}[a["signal"]]
        parts.append(f"{a['label']}: previsto {word}")
    return "; ".join(parts)
