"""Regole di legge sui contenuti: prodotti non pubblicizzabili, frasi vietate, premi della parola alla cassa."""
from __future__ import annotations

import pytest

from promovo.models import Offer
from promovo.modules import compliance as c


@pytest.mark.parametrize("name,desc,brand,code", [
    ("Sigarette", "pacchetto da 20", "", "tabacco"),
    ("Liquido per sigaretta elettronica", "10 ml", "", "tabacco"),
    ("Gratta e Vinci", "", "", "gioco"),
    ("Latte in polvere 1", "800 g", "Mellin", "lattanti"),
    ("Latte per lattanti liquido", "500 ml", "", "lattanti"),
    ("Tachipirina 500 mg", "20 compresse", "", "farmaci"),
])
def test_restricted_products(name, desc, brand, code):
    r = c.restriction(name, desc, brand)
    assert r is not None and r.code == code


@pytest.mark.parametrize("name,desc,brand", [
    ("Latte intero", "1 litro", "Granarolo"),
    ("Latte di crescita 3", "1 L", "Mellin"),                       # dai 12 mesi: non è latte per lattanti
    ("Omogeneizzato di mela", "2 x 100 g", "Plasmon"),
    ("Biscotti frollini", "350 g", ""),
    ("Vino rosso DOC", "75 cl", ""),
    ("Lotto di 3 saponette", "3 x 100 g", ""),
])
def test_ordinary_products_are_fine(name, desc, brand):
    assert c.restriction(name, desc, brand) is None


def test_restricted_offers_leave_every_promotional_list():
    from promovo.models import Flyer
    from promovo.modules.content.writer import available, featured_offers
    f = Flyer(title="x", pdf_path="x", pdf_sha256="x" * 64, page_count=1)
    f.offers = [Offer(name="Pasta", price_cents=79, position=0, page=1),
                Offer(name="Sigarette", price_cents=550, position=1, page=1),
                Offer(name="Latte per lattanti", description="800 g", price_cents=1590, position=2, page=1)]
    assert [o.name for o in available(f)] == ["Pasta"]
    assert [o.name for o in featured_offers(f)] == ["Pasta"]


@pytest.mark.parametrize("text", [
    "Partecipa al concorso: in palio una spesa gratis!",
    "Qui trovi i prezzi più bassi della città",
    "Prezzi imbattibili su tutta la frutta",
    "Più convenienti della concorrenza",
    "Lo yogurt che rinforza le difese immunitarie",
    "Mele a km zero",
    "Birra fresca per la merenda dei ragazzi",
])
def test_forbidden_phrases(text):
    assert c.text_issues(text)


@pytest.mark.parametrize("text", [
    "Spaghetti a € 0,79 invece di € 1,29: risparmi 50 centesimi.",
    "Vino rosso per la cena di sabato con gli amici.",
    "La provincia di Roma ci aspetta: siamo in via Latina 12.",          # «vinci» dentro «provincia»: va bene
    "Mozzarella del Caseificio Rossi, a 9 chilometri da qui.",
])
def test_ordinary_phrases_pass(text):
    assert c.text_issues(text) == []


def test_reward_must_be_a_discount():
    assert c.reward_issue("il 5% di sconto sulla spesa") is None
    assert c.reward_issue("1 € di sconto su una spesa di 15 €") is None
    for bad in ("un omaggio a sorpresa", "una borsa in regalo", "punti doppi sulla carta", "un caffè gratis"):
        assert c.reward_issue(bad)
    from promovo.modules import till
    with pytest.raises(ValueError, match="operazioni a premio"):
        till.clean_reward("un omaggio a sorpresa")


def test_reviewer_and_writer_reject_illegal_phrases():
    from promovo.modules.content.writer import review
    issues = review("Prezzi imbattibili! Spaghetti a € 0,79.", {79}, "familiare")
    assert any("regola di legge" in i for i in issues)


def test_proof_flags_restricted_products(session, store):
    from datetime import date
    from promovo.models import Flyer, FlyerStatus
    from promovo.modules import proof
    f = Flyer(store_id=store.id, title="Bozza", pdf_path="", pdf_sha256="y" * 64, page_count=1,
              status=FlyerStatus.ready, valid_from=date(2026, 12, 1), valid_to=date(2026, 12, 10))
    f.offers = [Offer(name="Sigarette", price_cents=550, position=0, page=1, price_verified=True),
                Offer(name="Latte per lattanti", description="800 g", price_cents=1590, position=1, page=1,
                      price_verified=True)]
    session.add(f)
    session.flush()
    rep = proof.check(session, store, f, today=date(2026, 11, 20))
    codes = {(x["code"], x["severity"]) for x in rep["findings"]}
    assert ("prodotto_vietato", "err") in codes and ("prodotto_vietato", "warn") in codes
