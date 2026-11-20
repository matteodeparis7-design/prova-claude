"""Banco e allergeni: proposta degli allergeni dagli ingredienti, conferma della persona, cartellini e registro."""
from __future__ import annotations

from promovo import pdfdoc
from fastapi.testclient import TestClient

from promovo.api import create_app
from promovo.db import Database
from promovo.modules import allergens as al

from conftest import FakeLLM, make_store, register


def test_detect_definite_doubts_and_traps():
    r = al.detect("pasta all'uovo, ragù, besciamella (latte, burro, farina), parmigiano, sedano, vino rosso")
    assert r["allergens"] == ["glutine", "uova", "latte", "sedano"]
    assert [d["code"] for d in r["doubts"]] == ["solfiti"] and "10 mg/kg" in r["doubts"][0]["why"]
    # falsi allarmi evitati: noce moscata e cocco non sono frutta a guscio, burro di cacao non è latte
    assert al.detect("zucchero, noce moscata, burro di cacao, latte di cocco, cocco rapé")["allergens"] == []
    # «senza glutine» non è un ingrediente
    assert "glutine" not in al.detect("farina di riso, amido di mais, senza glutine")["allergens"]
    # «farina» da sola: dubbio, non certezza
    r = al.detect("farina, zucchero, lievito")
    assert r["allergens"] == [] and r["doubts"][0]["code"] == "glutine"
    assert al.detect("calamari, gamberi, cozze")["allergens"] == ["crostacei", "molluschi"]
    r = al.detect("carne, uova, brodo vegetale, spezie")
    assert {"sedano", "senape"} <= {d["code"] for d in r["doubts"]}


def test_clean_requires_person_and_ingredients():
    import pytest
    with pytest.raises(al.AllergenError, match="chi ha controllato"):
        al.clean({"name": "Lasagne", "ingredients": "pasta, latte", "checked_by": ""})
    with pytest.raises(al.AllergenError, match="ingredienti"):
        al.clean({"name": "Lasagne", "ingredients": "", "checked_by": "Anna"})
    c = al.clean({"name": "Lasagne", "ingredients": "pasta, latte", "checked_by": "Anna",
                  "allergens": ["latte", "boh"], "may_contain": ["latte", "frutta_guscio"]})
    assert c["allergens"] == ["latte"] and c["may_contain"] == ["frutta_guscio"]     # niente doppioni né codici strani


def test_api_flow(tmp_settings):
    app = create_app(tmp_settings, llm=FakeLLM(), db=Database("sqlite://"))
    with TestClient(app) as c:
        h = register(c)
        s = make_store(c, h)
        d = c.post("/api/allergens/detect", headers=h, json={"ingredients": "pane, tonno, maionese, capperi"}).json()
        assert set(d["allergens"]) == {"glutine", "pesce", "uova"}
        r = c.post(f"/api/stores/{s['id']}/counter-items", headers=h,
                   json={"counter": "gastronomia", "name": "Tramezzino tonno e maionese",
                         "ingredients": "pane, tonno, maionese, capperi", "allergens": d["allergens"],
                         "may_contain": ["sesamo"], "checked_by": "Anna R."})
        assert r.status_code == 201, r.text
        a = r.json()
        assert a["checked_at"] and a["to_recheck"] == []
        # la persona dimentica un allergene evidente: Promovo lo segnala da ricontrollare
        b = c.post(f"/api/stores/{s['id']}/counter-items", headers=h,
                   json={"counter": "forno", "name": "Crostata", "ingredients": "farina di grano, burro, uova, marmellata",
                         "allergens": ["glutine", "uova"], "checked_by": "Luca"}).json()
        assert b["to_recheck"] == ["latte"]
        b = c.put(f"/api/counter-items/{b['id']}", headers=h,
                  json={**b, "allergens": ["glutine", "uova", "latte"], "checked_by": "Luca"}).json()
        assert b["to_recheck"] == []
        lst = c.get(f"/api/stores/{s['id']}/counter-items", headers=h).json()
        assert len(lst["items"]) == 2 and len(lst["allergens"]) == 14
        reg = c.get(f"/api/stores/{s['id']}/allergens/registro.pdf", headers=h)
        assert reg.status_code == 200 and reg.content[:4] == b"%PDF"
        assert pdfdoc.open(stream=reg.content, filetype="pdf")[0].rect.width > 800      # A4 orizzontale
        lab = c.get(f"/api/stores/{s['id']}/allergens/cartellini.pdf?counter=forno", headers=h)
        assert lab.status_code == 200
        assert c.get(f"/api/stores/{s['id']}/allergens/cartello.pdf", headers=h).status_code == 200
        assert c.get(f"/api/stores/{s['id']}/allergens/cartellini.pdf?counter=pescheria", headers=h).status_code == 404
        h2 = register(c, email="altro@test.it", org="Altra")
        assert c.delete(f"/api/counter-items/{a['id']}", headers=h2).status_code == 404
        assert c.delete(f"/api/counter-items/{a['id']}", headers=h).status_code == 204
