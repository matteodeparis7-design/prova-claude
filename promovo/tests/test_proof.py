"""Correttore del volantino: gli errori della bozza trovati prima della stampa."""
from __future__ import annotations

from datetime import date

from promovo import pdfdoc
from fastapi.testclient import TestClient

from promovo.api import create_app
from promovo.db import Database
from promovo.modules import proof
from promovo.modules.flyer.service import ingest_flyer
from promovo.sample_flyer import FlyerStyle, SampleProduct, build_sample_flyer

from conftest import TODAY, FakeLLM, make_store, register, upload

C = (200, 160, 90)


def _codes(rep, name=None):
    return {f["code"] for f in rep["findings"] if name is None or name.lower() in f["offer"].lower()}


def test_unit_price_missing_and_wrong(session, store, tmp_settings):
    # volantino senza prezzo al kg: va segnalato per le confezioni, non per «al kg», 1 litro e i lavaggi
    f = ingest_flyer(session, store, build_sample_flyer(), tmp_settings, None, today=TODAY)
    rep = proof.check(session, store, f, today=TODAY)
    assert rep["text_pdf"]
    assert "unitario_mancante" in _codes(rep, "spaghetti")
    for ok in ("pollo", "olio", "detersivo", "mele"):
        assert "unitario_mancante" not in _codes(rep, ok), ok
    msg = next(x["message"] for x in rep["findings"] if x["code"] == "unitario_mancante" and "Spaghetti" in x["offer"])
    assert "€ 1,58 al kg" in msg
    # prezzo al kg stampato sbagliato: il generatore scrive sempre il doppio del prezzo (giusto solo per 500 g)
    g = ingest_flyer(session, store, build_sample_flyer(style=FlyerStyle(unit_price=True),
                                                        validity="Offerte valide dal 13 al 22 novembre 2026 "),
                     tmp_settings, None, today=TODAY)
    rep2 = proof.check(session, store, g, today=TODAY)
    assert "unitario_sbagliato" in _codes(rep2, "passata")          # 700 g: stampato 1,98, giusto 1,41
    assert "unitario_sbagliato" not in _codes(rep2, "spaghetti")    # 500 g: 1,58 è giusto
    assert "unitario_mancante" not in _codes(rep2, "spaghetti")


def test_discount_barred_typo_duplicate_format(session, store, tmp_settings):
    week1 = [SampleProduct("Caffè macinato", "250 g", 249, None, C), SampleProduct("Biscotti frollini", "350 g", 129, None, C)]
    ingest_flyer(session, store, build_sample_flyer(week1, validity="Offerte valide dal 1 al 10 novembre 2026"),
                 tmp_settings, None, today=date(2026, 11, 2))
    week2 = [SampleProduct("Caffè macinato", "250 g", 2490, None, C),             # refuso: 24,90 invece di 2,49
             SampleProduct("Passata di pomodoro", "700 g", 99, 149, C),
             SampleProduct("Tonno all'olio", "3 x 80 g", 299, None, C),
             SampleProduct("Tonno all'olio", "3 x 80 g", 349, None, C),            # doppione con prezzo diverso
             SampleProduct("Biscotti frollini", "", 129, None, C)]                # formato mancante
    f = ingest_flyer(session, store, build_sample_flyer(week2, validity="Offerte valide dal 13 al 22 novembre 2026"),
                     tmp_settings, None, today=TODAY)
    rep = proof.check(session, store, f, today=TODAY)
    assert "refuso" in _codes(rep, "caffè")
    assert "doppione" in _codes(rep, "tonno")
    assert "formato_mancante" in _codes(rep, "biscotti")
    assert "sconto_sbagliato" not in _codes(rep) and "barrato_basso" not in _codes(rep)
    # sconto stampato -34% ma il prezzo barrato cambia: lo sconto vero non torna più
    passata = next(o for o in f.offers if "Passata" in o.name)
    passata.old_price_cents = 199
    session.flush()
    rep = proof.check(session, store, f, today=TODAY)
    assert "sconto_sbagliato" in _codes(rep, "passata")
    passata.old_price_cents = 99                                                   # barrato uguale al prezzo
    session.flush()
    assert "barrato_basso" in _codes(proof.check(session, store, f, today=TODAY), "passata")
    assert rep["counts"]["err"] >= 3 and "da correggere" in rep["verdict"]


def test_dates(session, store, tmp_settings):
    f = ingest_flyer(session, store, build_sample_flyer(validity="Le nostre offerte"), tmp_settings, None, today=TODAY)
    assert "date_mancanti" in _codes(proof.check(session, store, f, today=TODAY))
    f.valid_from, f.valid_to = date(2026, 11, 20), date(2026, 11, 10)
    assert "date_invertite" in _codes(proof.check(session, store, f, today=TODAY))
    f.valid_from, f.valid_to = date(2026, 10, 1), date(2026, 10, 10)
    assert "date_passate" in _codes(proof.check(session, store, f, today=TODAY))


def test_api_and_pdf(tmp_settings, live_pdf):
    app = create_app(tmp_settings, llm=FakeLLM(), db=Database("sqlite://"))
    with TestClient(app) as c:
        h = register(c)
        s = make_store(c, h)
        f = upload(c, h, s["id"], live_pdf)
        rep = c.get(f"/api/flyers/{f['id']}/proof", headers=h).json()
        assert rep["offers"] == 12 and rep["counts"]["err"] >= 1 and rep["findings"]
        pdf = c.get(f"/api/flyers/{f['id']}/proof.pdf", headers=h)
        assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
        text = "".join(p.get_text() for p in pdfdoc.open(stream=pdf.content, filetype="pdf"))
        assert "Rapporto di correzione" in text and "al kg" in text
        h2 = register(c, email="altro@test.it", org="Altra")
        assert c.get(f"/api/flyers/{f['id']}/proof", headers=h2).status_code == 404
