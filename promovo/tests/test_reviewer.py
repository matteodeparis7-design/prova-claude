"""Revisore finale: il controllo di qualità dei materiali prima della consegna."""
from __future__ import annotations

from pathlib import Path

from promovo.models import ContentPiece
from promovo.modules.content.service import generate_content, save_content
from promovo.modules.flyer.service import ingest_flyer
from promovo.modules.graphics.service import render_flyer_images
from promovo.modules.reviewer import review

from conftest import TODAY


def _setup(session, store, sample_pdf, tmp_settings):
    f = ingest_flyer(session, store, sample_pdf, tmp_settings, None, today=TODAY)
    save_content(session, store, f, generate_content(store, f, None, today=TODAY))
    render_flyer_images(session, store, f, tmp_settings)
    session.flush()
    return f


def test_review_passes_good_materials(session, store, sample_pdf, tmp_settings):
    f = _setup(session, store, sample_pdf, tmp_settings)
    r = review(session, store, f)
    assert r["verdict"] == "pronto da consegnare", [c for c in r["checks"] if c["status"] != "ok"]
    assert r["counts"]["err"] == 0 and r["counts"]["ok"] >= 10
    areas = {c["area"] for c in r["checks"]}
    assert {"offerte", "grafiche", "testi"} <= areas


def test_review_finds_stale_missing_and_wrong(session, store, sample_pdf, tmp_settings):
    f = _setup(session, store, sample_pdf, tmp_settings)
    o = f.offers[0]
    o.price_cents += 10                                    # prezzo corretto dopo aver fatto i materiali
    session.flush()
    r = review(session, store, f)
    stale = [c for c in r["checks"] if "prima che cambiassi il prezzo" in c["message"]]
    assert stale and o.name in stale[0]["message"] and r["verdict"] == "da sistemare"
    assert all("Rifai i materiali" in c["message"] for c in stale)
    o.price_cents -= 10
    session.flush()
    img = session.query(ContentPiece).filter_by(flyer_id=f.id, kind="image").first()
    Path(img.file_path).unlink()                           # grafica sparita
    ig = session.query(ContentPiece).filter_by(flyer_id=f.id, kind="instagram").first()
    ig.body += "\nSolo oggi a € 0,01!"                     # prezzo che non esiste
    session.flush()
    r = review(session, store, f)
    msgs = " | ".join(c["message"] for c in r["checks"] if c["status"] == "err")
    assert "manca o è vuoto" in msgs and "€ 0,01" in msgs
