"""Agente Omnibus: il prezzo barrato confrontato con il minimo dei 30 giorni prima (volantini del negozio)."""
from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from promovo.api import create_app
from promovo.db import Database
from promovo.models import Flyer, FlyerStatus, Offer
from promovo.modules import omnibus

from conftest import FakeLLM, make_store, register, upload


def _flyer(session, store, start, end, offers, competitor=""):
    f = Flyer(store_id=store.id, title=f"Volantino {start}", pdf_path="", pdf_sha256="x", page_count=1,
              status=FlyerStatus.ready, valid_from=start, valid_to=end, competitor=competitor)
    session.add(f)
    session.flush()
    for i, (name, desc, price, old) in enumerate(offers):
        session.add(Offer(flyer_id=f.id, name=name, description=desc, price_cents=price, old_price_cents=old,
                          category="altro", page=1, position=i, bbox=[0, 0, 1, 1]))
    session.flush()
    session.refresh(f)
    return f


def test_omnibus_finds_wrong_struck_prices(session, store):
    _flyer(session, store, date(2026, 10, 20), date(2026, 10, 30), [
        ("Spaghetti di grano duro", "500 g", 79, 129),
        ("Caffè macinato", "250 g", 219, 349),
        ("Riso arborio", "1 kg", 200, None),
        ("Olio extravergine", "1 litro", 499, 799),
    ])
    # concorrente e volantini troppo vecchi non contano
    _flyer(session, store, date(2026, 10, 20), date(2026, 10, 30), [("Biscotti frollini", "350 g", 50, None)], competitor="Altro")
    _flyer(session, store, date(2026, 9, 1), date(2026, 9, 10), [("Biscotti frollini", "350 g", 60, None)])
    now = _flyer(session, store, date(2026, 11, 13), date(2026, 11, 22), [
        ("Spaghetti di grano duro", "500 g", 99, 129),      # era a 0,79: non è uno sconto
        ("Caffè macinato", "250 g", 199, 349),              # minimo 2,19: barrato da correggere
        ("Riso arborio", "500 g", 89, 129),                 # 1 kg a 2,00 = 1,00 per 500 g
        ("Olio extravergine", "1 litro", 499, 799),         # stesso prezzo di prima, barrato già alto
        ("Biscotti frollini", "350 g", 99, 149),            # nessun prezzo nei 30 giorni: niente da dire
        ("Acqua naturale", "6 x 1,5 L", 189, None),         # nessun barrato: niente da controllare
    ])
    found = {x.offer.name: x for x in omnibus.check(session, store, now)}
    assert set(found) == {"Spaghetti di grano duro", "Caffè macinato", "Riso arborio", "Olio extravergine"}
    assert found["Spaghetti di grano duro"].lowest_cents == 79
    d = found["Spaghetti di grano duro"].as_dict()
    assert d["true_discount"] == 0 and "non è uno sconto" in d["message"] and "dal 20/10 al 30/10" in d["message"]
    c = found["Caffè macinato"].as_dict()
    assert c["lowest_cents"] == 219 and c["true_discount"] == 9 and "€ 2,19" in c["message"]
    assert found["Riso arborio"].lowest_cents == 100                    # riportato al formato di adesso
    s = omnibus.summary(session, store, now)
    assert s["checked"] and s["previous_flyers"] == 1 and s["barred"] == 5 and len(s["findings"]) == 4


def test_omnibus_without_history_says_nothing(session, store):
    now = _flyer(session, store, date(2026, 11, 13), date(2026, 11, 22), [("Pasta", "500 g", 79, 129)])
    assert omnibus.check(session, store, now) == []
    assert omnibus.summary(session, store, now)["checked"] is False


def test_api_omnibus_and_fix(tmp_settings, live_pdf):
    app = create_app(tmp_settings, llm=FakeLLM(), db=Database("sqlite://"))
    with TestClient(app) as c:
        h = register(c)
        st = make_store(c, h)
        old = upload(c, h, st["id"], live_pdf)
        new = upload(c, h, st["id"], live_pdf)
        # il volantino «vecchio» diventa quello di due settimane prima, a prezzi più bassi
        with app.state.promovo.db.session() as s:
            fo, fn = s.get(Flyer, old["id"]), s.get(Flyer, new["id"])
            fo.valid_from, fo.valid_to = date(2026, 10, 20), date(2026, 10, 30)
            fn.valid_from, fn.valid_to = date(2026, 11, 13), date(2026, 11, 22)
            for o in fo.offers:
                o.price_cents = max(10, o.price_cents - 30)
            s.commit()
        r = c.get(f"/api/flyers/{new['id']}/omnibus", headers=h).json()
        assert r["checked"] and r["findings"]
        x = r["findings"][0]
        fix = f"{x['lowest_cents'] / 100:.2f}".replace(".", ",") if x["true_discount"] else ""
        assert c.patch(f"/api/offers/{x['offer_id']}", headers=h, json={"old_price": fix}).status_code == 200
        r2 = c.get(f"/api/flyers/{new['id']}/omnibus", headers=h).json()
        assert x["offer_id"] not in {y["offer_id"] for y in r2["findings"]}
        rep = c.get(f"/api/flyers/{new['id']}/report.pdf", headers=h)
        assert rep.status_code == 200
        from promovo import pdfdoc
        text = " ".join(" ".join(p.get_text() for p in pdfdoc.open(stream=rep.content, filetype="pdf")).split())
        assert "Controllo automatico con il volantino precedente del negozio" in text
