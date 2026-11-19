"""Prova dal vivo: i supermercati veri intorno a un indirizzo (OpenStreetMap) e il meteo della città.

Uso: python tools/check_nearby.py "Via Roma 1" Colleferro
"""
import sys

from promovo.models import Store
from promovo.modules.radar import nearby as nb
from promovo.modules.weather import service as w

address, city = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else ("", sys.argv[1] if len(sys.argv) > 1 else "Colleferro")
store = Store(name="Prova", address=address, city=city)
for url in nb.OVERPASS_URLS:      # quali server della mappa rispondono da qui
    try:
        n = len(nb.http_json(url, {"data": "[out:json];node(41.729,13.003,41.730,13.005);out 1;"}, timeout=15).get("elements", []))
        print(f"  server {url}: risponde")
    except nb.NearbyUnavailable as exc:
        print(f"  server {url}: {exc}")
res = nb.nearby(store, 3000)
c = res["center"]
print(f"Centro: {c['lat']:.5f}, {c['lon']:.5f} (da {c['precision']}) - {len(res['places'])} negozi entro 3 km")
for p in res["places"]:
    print(f"  {p['distance_m']:>5} m  {p['kind']:<13} {p['label']}  [{p['address']}]")
lat, lon, name = w.geocode(city)
print(f"Meteo: {name} -> {lat:.3f}, {lon:.3f}; giorni: {len(w.forecast(lat, lon))}")
