"""«Esaurito»: il prodotto finito esce dai materiali nuovi del punto vendita."""
from __future__ import annotations

import io

from fastapi.testclient import TestClient
from PIL import Image

from promovo.api import create_app
from promovo.db import Database
from promovo.models import ContentPiece
from promovo.modules import soldout
from promovo.modules.content.service import featured_offers, generate_content, save_content
from promovo.modules.flyer.service import ingest_flyer
from promovo.modules.graphics.service import render_flyer_images
from promovo.modules.reviewer import review
from promovo.modules.video.service import spec_offers

from conftest import TODAY, FakeLLM, make_store, register, upload


def test_sold_out_leaves_new_materials_and_flags_old(session, store, sample_pdf, tmp_settings):
    f = ingest_flyer(session, store, sample_pdf, tmp_settings, None, today=TODAY)
    save_content(session, store, f, generate_content(store, f, None, today=TODAY))
    render_flyer_images(session, store, f, tmp_settings)
    session.flush()
    top = featured_offers(f, 6)[0]
    soldout.mark(top, True, "Torna giovedì")
    session.flush()
    assert top not in featured_offers(f, 6) and top not in spec_offers(f, "landscape")
    stale = soldout.stale_pieces(session, f)
    kinds = {s["kind"] for s in stale}
    assert "image" in kinds and all(top.name in s["offers"] for s in stale)
    pieces = list(session.query(ContentPiece).filter_by(flyer_id=f.id))
    assert "images" in soldout.remake_items(stale, pieces)
    r = review(session, store, f)
    assert any("segnato esaurito" in c["message"] for c in r["checks"]) and r["verdict"] == "da sistemare"
    # rifatte le grafiche: il prodotto non c'è più e niente da segnalare per le immagini
    render_flyer_images(session, store, f, tmp_settings)
    save_content(session, store, f, generate_content(store, f, None, today=TODAY))
    session.flush()
    assert not [s for s in soldout.stale_pieces(session, f) if s["kind"] in ("image", "instagram", "facebook")]
    for p in session.query(ContentPiece).filter_by(flyer_id=f.id, kind="image"):
        assert top.id not in (p.meta or {}).get("offer_ids", [])
    text = soldout.message_text(store, top)
    assert "esaurito" in text.lower() and "Torna giovedì." in text
    assert soldout.message_image(store, top).size == (1080, 1350)
    # di nuovo disponibile
    soldout.mark(top, False)
    assert top.sold_out_at is None and top in featured_offers(f, 6)


def test_api_and_network(tmp_settings, live_pdf):
    app = create_app(tmp_settings, llm=FakeLLM(), db=Database("sqlite://"))
    with TestClient(app) as c:
        h = register(c)
        s1 = make_store(c, h)
        s2 = make_store(c, h, name="Superstore Segni", city="Segni")
        f1 = upload(c, h, s1["id"], live_pdf)
        f2 = upload(c, h, s2["id"], live_pdf)
        c.post(f"/api/flyers/{f1['id']}/content", headers=h)
        st = c.get(f"/api/flyers/{f1['id']}/sold-out", headers=h).json()
        assert st["stale"] == [] and not any(o["sold_out"] for o in st["offers"])
        o = st["offers"][0]
        st = c.post(f"/api/offers/{o['id']}/sold-out", headers=h, json={"sold_out": True, "note": "Torna lunedì"}).json()
        mine = next(x for x in st["offers"] if x["id"] == o["id"])
        assert mine["sold_out"] and mine["sold_out_note"] == "Torna lunedì"
        msg = c.get(f"/api/offers/{o['id']}/sold-out-message", headers=h).json()
        assert "Torna lunedì" in msg["text"]
        img = c.get(msg["image_url"], headers=h)
        assert Image.open(io.BytesIO(img.content)).size == (1080, 1350)
        o2 = c.get(f"/api/flyers/{f2['id']}/sold-out", headers=h).json()["offers"][1]
        c.post(f"/api/offers/{o2['id']}/sold-out", headers=h, json={"sold_out": True})
        net = c.get("/api/sold-out-network", headers=h).json()["rows"]
        assert {r["store"] for r in net} == {"Superstore Colleferro", "Superstore Segni"}
        assert all(r["day_of_flyer"] == 2 for r in net)          # volantino iniziato ieri: finito al 2° giorno
        h2 = register(c, email="altro@test.it", org="Altra")
        assert c.get("/api/sold-out-network", headers=h2).json()["rows"] == []
        assert c.post(f"/api/offers/{o['id']}/sold-out", headers=h2, json={"sold_out": False}).status_code == 404
        st = c.post(f"/api/offers/{o['id']}/sold-out", headers=h, json={"sold_out": False}).json()
        assert not next(x for x in st["offers"] if x["id"] == o["id"])["sold_out"]
