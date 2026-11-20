"""Filiera vicina: produttori del territorio con la distanza vera, post, mappa, etichette."""
from __future__ import annotations

import io

from promovo import pdfdoc
from fastapi.testclient import TestClient
from PIL import Image

from promovo.api import create_app
from promovo.db import Database
from promovo.modules import filiera
from promovo.modules import geo as nb

from conftest import FakeLLM, make_store, register, upload

PLACES = {"colleferro": (41.7305, 13.0030), "paliano": (41.8070, 13.0590), "segni": (41.6920, 13.0390),
          "anagni": (41.7430, 13.1580)}


def fake_map(url, params):
    text = " ".join(str(v) for v in params.values()).lower()
    for name, (lat, lon) in PLACES.items():
        if name in text:
            return [{"lat": str(lat), "lon": str(lon), "name": name.title(), "address": {"town": name.title()}}]
    return []


def test_clean_and_text():
    import pytest
    with pytest.raises(filiera.FilieraError):
        filiera.clean({"name": "X", "town": "Paliano", "what": "formaggi"})
    with pytest.raises(filiera.FilieraError, match="comune"):
        filiera.clean({"name": "Caseificio", "town": "", "what": "formaggi"})
    with pytest.raises(filiera.FilieraError, match="consenso"):
        filiera.clean({"name": "Caseificio Rossi", "town": "Paliano", "what": "formaggi"})
    assert filiera.clean({"name": "Caseificio Rossi", "town": "Paliano", "what": "formaggi", "consent": "true"})
    assert filiera.km_text(0.4) == "a meno di 1 km da qui" and filiera.km_text(12.3) == "a circa 12 km da qui"


def test_api_flow(tmp_settings, live_pdf):
    nb._cache.clear()
    app = create_app(tmp_settings, llm=FakeLLM(), db=Database("sqlite://"))
    app.state.promovo.nearby_fetch = fake_map
    with TestClient(app) as c:
        h = register(c)
        s = make_store(c, h)                              # Colleferro
        f = upload(c, h, s["id"], live_pdf)
        offers = c.get(f"/api/flyers/{f['id']}", headers=h).json()["offers"]
        word = offers[0]["name"].split()[0]
        buf = io.BytesIO()
        Image.new("RGB", (900, 700), (180, 150, 110)).save(buf, "JPEG")
        r = c.post(f"/api/stores/{s['id']}/producers", headers=h,
                   data={"consent": "true", "name": "Caseificio Rossi", "town": "Paliano", "what": "mozzarella e ricotta",
                         "story": "Lavorano il latte delle loro mucche dal 1962", "keywords": word},
                   files={"photo": ("rossi.jpg", buf.getvalue(), "image/jpeg")})
        assert r.status_code == 201, r.text
        a = r.json()
        assert 8 < a["km"] < 11 and a["km_text"].startswith("a circa") and a["photo_url"]
        assert a["offers"] and a["offers"][0]["name"] == offers[0]["name"]       # riconosciuto nel volantino
        assert "Caseificio Rossi, a Paliano, a circa" in a["text"] and "dal 1962" in a["text"]
        assert "in offerta" in a["text"] and "#Paliano" in a["text"] and "km 0" not in a["text"].lower()
        b = c.post(f"/api/stores/{s['id']}/producers", headers=h,
                   data={"consent": "true", "name": "Orto Bianchi", "town": "Segni", "what": "verdura di stagione"}).json()
        assert b["km"] is not None and not b["offers"]
        # comune che non esiste: salvato con l'errore da mostrare, nessuna distanza inventata
        x = c.post(f"/api/stores/{s['id']}/producers", headers=h,
                   data={"consent": "true", "name": "Apicoltura Verdi", "town": "Paesinventato", "what": "miele"}).json()
        assert x["km"] is None and "Paesinventato" in x["geo_error"]
        assert c.get(f"/api/stores/{s['id']}/producers", headers=h).json()["week"] != x["id"]    # mai senza distanza
        # correzione del comune: ricalcola
        x = c.put(f"/api/producers/{x['id']}", headers=h,
                  data={"consent": "true", "name": "Apicoltura Verdi", "town": "Anagni", "what": "miele"}).json()
        assert x["km"] is not None and x["geo_error"] == ""
        lst = c.get(f"/api/stores/{s['id']}/producers", headers=h).json()
        assert [p["name"] for p in lst["items"]][0] == "Orto Bianchi"             # dal più vicino
        assert lst["week"] == a["id"]                                             # prima chi è nel volantino
        assert lst["located"] == 3
        post = c.get(a["post_url"], headers=h)
        assert Image.open(io.BytesIO(post.content)).size == (1080, 1350)
        mp = c.get(f"/api/stores/{s['id']}/producers-map.jpg", headers=h)
        assert mp.status_code == 200 and Image.open(io.BytesIO(mp.content)).size == (1080, 1350)
        pdf = c.get(f"/api/stores/{s['id']}/producers-labels", headers=h)
        assert pdf.status_code == 200 and pdfdoc.open(stream=pdf.content, filetype="pdf").page_count == 1
        # privacy tra account
        h2 = register(c, email="altro@test.it", org="Altra")
        assert c.get(a["post_url"], headers=h2).status_code == 404
        assert c.delete(f"/api/producers/{a['id']}", headers=h2).status_code == 404
        assert c.delete(f"/api/producers/{a['id']}", headers=h).status_code == 204
        assert len(c.get(f"/api/stores/{s['id']}/producers", headers=h).json()["items"]) == 2
