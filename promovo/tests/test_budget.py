"""Calendario dei portafogli e spesa a budget: cestino vero con il totale al centesimo."""
from __future__ import annotations

import io
from datetime import date

from fastapi.testclient import TestClient
from PIL import Image

from promovo.api import create_app
from promovo.db import Database
from promovo.models import Flyer, Offer
from promovo.modules import budget

from conftest import FakeLLM, make_store, register, upload


def _o(i, name, cat, price, old=None, desc=""):
    return Offer(id=i, name=name, category=cat, price_cents=price, old_price_cents=old, description=desc,
                 page=1, position=i, price_verified=True,
                 discount_percent=round((old - price) * 100 / old) if old else None)


def test_moment_and_best_day():
    assert budget.moment(date(2026, 11, 3))["key"] == "scorta"
    assert budget.moment(date(2026, 11, 12))["key"] == "regolare"
    assert budget.moment(date(2026, 11, 22))["key"] == "budget"
    assert budget.moment(date(2026, 11, 28))["key"] == "stipendi"
    assert budget.moment(date(2026, 12, 10))["key"] == "tredicesima"
    f = Flyer(valid_from=date(2026, 11, 16), valid_to=date(2026, 11, 27))
    d, why = budget.best_day(f, date(2026, 11, 16))
    assert d == date(2026, 11, 20) and "fine mese" in why          # giovedì 20, a fine mese
    f2 = Flyer(valid_from=date(2026, 11, 2), valid_to=date(2026, 11, 8))
    d2, _ = budget.best_day(f2, date(2026, 11, 2))
    assert d2.weekday() in (3, 4)


def test_basket_is_exact_varied_and_safe():
    offers = [_o(1, "Spaghetti", "pasta e riso", 79, 129, "500 g"), _o(2, "Penne", "pasta e riso", 69, None, "500 g"),
              _o(3, "Latte", "latte e latticini", 99, 139, "1 litro"), _o(4, "Uova", "uova", 189, 239, "6 pezzi"),
              _o(5, "Mele", "frutta e verdura", 149, None, "1,5 kg"), _o(6, "Petto di pollo", "carne", 799, 1090),
              _o(7, "Detersivo", "igiene casa", 399, 650), _o(8, "Vino rosso", "vino e alcolici", 349, 499),
              _o(9, "Biscotti", "colazione", 129, 199, "350 g")]
    b = budget.make_basket(offers, 1000)
    names = [o.name for o in b.items]
    assert b.total <= 1000 and b.total == sum(o.price_cents for o in b.items)
    assert names.index("Penne") < names.index("Spaghetti")             # prima il più conveniente del reparto
    assert "Detersivo" not in names and "Vino rosso" not in names      # niente casa e alcolici nella spesa
    assert {"pasta e riso", "latte e latticini", "uova", "frutta e verdura"} <= {o.category for o in b.items}
    assert b.saving == sum(o.old_price_cents - o.price_cents for o in b.items if o.old_price_cents)
    assert budget.make_basket(offers, 150) is None                     # meno di 3 prodotti: niente
    assert 10 in budget.amounts_for(offers) and 50 in budget.amounts_for(offers)


def test_api(tmp_settings, live_pdf):
    app = create_app(tmp_settings, llm=FakeLLM(), db=Database("sqlite://"))
    with TestClient(app) as c:
        h = register(c)
        s = make_store(c, h)
        f = upload(c, h, s["id"], live_pdf)
        r = c.get(f"/api/flyers/{f['id']}/budget", headers=h).json()
        assert r["moment"]["advice"] and r["best_day"] and r["amounts"]
        assert r["amount"] in r["amounts"] and r["basket"]["items"]
        assert "La spesa a" in r["text"] and r["basket"]["total"] in r["text"]
        img = c.get(r["image_url"], headers=h)
        assert img.status_code == 200 and Image.open(io.BytesIO(img.content)).size == (1080, 1350)
        assert c.get(f"/api/flyers/{f['id']}/budget.jpg?amount=1", headers=h).status_code == 404
        h2 = register(c, email="altro@test.it", org="Altra")
        assert c.get(f"/api/flyers/{f['id']}/budget", headers=h2).status_code == 404
