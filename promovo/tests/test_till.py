"""Parola alla cassa: parole d'ordine per canale nei testi e clienti contati alla cassa."""
from __future__ import annotations

from datetime import date, timedelta

from promovo import pdfdoc
from fastapi.testclient import TestClient

from promovo.api import create_app
from promovo.db import Database
from promovo.models import ContentPiece
from promovo.modules import till

from conftest import FakeLLM, make_store, register, upload


def test_full_flow(tmp_settings, live_pdf):
    app = create_app(tmp_settings, llm=FakeLLM(), db=Database("sqlite://"))
    today = date.today()
    with TestClient(app) as c:
        h = register(c)
        s = make_store(c, h)
        f = upload(c, h, s["id"], live_pdf)
        c.post(f"/api/flyers/{f['id']}/content", headers=h)
        st = c.get(f"/api/stores/{s['id']}/till", headers=h).json()
        assert st["on"] is False and st["flyer"]["id"] == f["id"]
        words = [r["word"] for r in st["results"]["rows"]]
        assert len(set(words)) == 4                                         # una parola diversa per canale
        offer_words = " ".join(o["name"].lower() for o in c.get(f"/api/flyers/{f['id']}", headers=h).json()["offers"])
        assert not any(w.lower() in offer_words for w in words)             # mai un prodotto in offerta
        # accesa: la parola compare nei testi del volantino, prima degli hashtag
        bad = c.put(f"/api/stores/{s['id']}/till", headers=h, json={"on": True, "reward": "x"})
        assert bad.status_code == 400
        st = c.put(f"/api/stores/{s['id']}/till", headers=h,
                   json={"on": True, "reward": "1 € di sconto su una spesa di 15 €"}).json()
        assert st["on"]
        ws = {r["channel"]: r["word"] for r in st["results"]["rows"]}
        content = c.get(f"/api/flyers/{f['id']}/content", headers=h).json()
        ig = next(x for x in content if x["kind"] == "instagram")["body"]
        fb = next(x for x in content if x["kind"] == "facebook")["body"]
        assert f"«{ws['instagram']}» alla cassa" in ig and f"«{ws['facebook']}» alla cassa" in fb
        assert "1 € di sconto" in ig
        tail = ig.strip().split("\n\n")
        if tail[-1].lstrip().startswith("#"):
            assert "alla cassa" in tail[-2]
        # rifacendo i testi la riga non si duplica
        c.post(f"/api/flyers/{f['id']}/content", headers=h)
        ig2 = next(x for x in c.get(f"/api/flyers/{f['id']}/content", headers=h).json() if x["kind"] == "instagram")["body"]
        assert ig2.count("alla cassa") == 1
        # il premio («1 €», «15 €») non è segnalato dal Revisore come prezzo inesistente
        rv = c.get(f"/api/flyers/{f['id']}/review", headers=h).json()
        assert not any("Prezzi che non sono nel volantino" in x["message"] for x in rv["checks"])
        # conteggi alla cassa
        rows = {r["channel"]: r for r in st["results"]["rows"]}
        for _ in range(3):
            c.post(f"/api/till/{rows['whatsapp']['code_id']}/hit", headers=h, json={"delta": 1})
        c.post(f"/api/till/{rows['whatsapp']['code_id']}/hit", headers=h, json={"delta": -1})
        assert c.post(f"/api/till/{rows['whatsapp']['code_id']}/hit", headers=h, json={"delta": 5}).status_code == 400
        day = st["results"]["days"][0]
        c.put(f"/api/till/{rows['instagram']['code_id']}/count", headers=h, json={"day": day, "count": 9})
        c.put(f"/api/till/{rows['facebook']['code_id']}/count", headers=h, json={"day": day, "count": 1})
        st = c.get(f"/api/stores/{s['id']}/till", headers=h).json()
        tot = {r["channel"]: r["total"] for r in st["results"]["rows"]}
        assert tot == {"instagram": 9, "facebook": 1, "whatsapp": 2, "reel": 0} and st["results"]["total"] == 12
        assert any("Instagram porta più clienti" in a for a in st["advice"])
        assert any("Reel e TikTok" in a for a in st["advice"])
        # nel report per il cliente
        rep = c.get(f"/api/flyers/{f['id']}/report.pdf", headers=h)
        rtext = "".join(pg.get_text() for pg in pdfdoc.open(stream=rep.content, filetype="pdf"))
        assert "Parola alla cassa" in rtext and "12 clienti" in rtext
        # foglio per la cassa
        pdf = c.get(f"/api/stores/{s['id']}/till-sheet", headers=h)
        assert pdf.status_code == 200
        text = pdfdoc.open(stream=pdf.content, filetype="pdf")[0].get_text()
        assert pdf.content[:4] == b"%PDF"
        # spenta: la riga sparisce dai testi
        c.put(f"/api/stores/{s['id']}/till", headers=h, json={"on": False})
        ig3 = next(x for x in c.get(f"/api/flyers/{f['id']}/content", headers=h).json() if x["kind"] == "instagram")["body"]
        assert "alla cassa" not in ig3
        # un altro account non può contare sulle parole altrui
        h2 = register(c, email="altro@test.it", org="Altra")
        assert c.post(f"/api/till/{rows['whatsapp']['code_id']}/hit", headers=h2, json={"delta": 1}).status_code == 404
        del text


def test_words_change_between_flyers_and_strip(session, store, sample_pdf, tmp_settings):
    from promovo.modules.flyer.service import ingest_flyer
    from conftest import TODAY
    f1 = ingest_flyer(session, store, sample_pdf, tmp_settings, None, today=TODAY)
    w1 = {c.word for c in till.codes_for(session, store, f1).values()}
    assert till.codes_for(session, store, f1)["instagram"].word in w1        # sempre le stesse per lo stesso volantino
    f2 = ingest_flyer(session, store, sample_pdf.replace(b"%%EOF", b"% altro\n%%EOF"), tmp_settings, None, today=TODAY)
    w2 = {c.word for c in till.codes_for(session, store, f2).values()}
    assert not (w1 & w2)                                                     # il volantino dopo usa parole nuove
    body = "Testo.\n\n🔑 Dì «ARANCIA» alla cassa: per te il 5% di sconto sulla spesa.\n\n#spesa"
    assert till.strip(body) == "Testo.\n\n#spesa"
    assert till.clean_reward("  il 10% di sconto.  ") == "il 10% di sconto"
