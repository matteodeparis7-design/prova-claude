from datetime import date, datetime, timedelta, timezone

import pytest

from promovo.models import ApiToken, Organization, User
from promovo.money import discount_percent, find_prices, format_eur, parse_price, price_parts
from promovo.security import hash_password, issue_token, revoke_token, user_for_token, verify_password
from promovo.text_utils import categorize, coerce_category, parse_validity, similarity


@pytest.mark.parametrize("text,cents", [
    ("1,99", 199), ("€ 1,99", 199), ("1.99€", 199), ("12,90", 1290), ("1.299,00", 129900), ("0,79", 79),
    ("3", 300), (2, 200), (1.1, 110), (0.29, 29), ("€ 4,50", 450),
])
def test_parse_price(text, cents):
    assert parse_price(text) == cents


@pytest.mark.parametrize("text", ["", "abc", None, "-", "1,9a", True, -3])
def test_parse_price_invalid(text):
    assert parse_price(text) is None


def test_find_prices_and_format():
    assert find_prices("Pasta 0,79 invece di 1,29 - al kg 1,58") == [79, 129, 158]
    assert find_prices("formato 1,5 L e 500 g") == []
    assert format_eur(0) == "€ 0,00"
    assert format_eur(123456) == "€ 1.234,56"
    assert format_eur(-5) == "-€ 0,05"
    assert format_eur(None) == ""
    assert price_parts(1299) == ("12", "99")


def test_discount_percent():
    assert discount_percent(79, 129) == 39
    assert discount_percent(100, 100) is None
    assert discount_percent(100, 90) is None
    assert discount_percent(100, None) is None
    assert discount_percent(50, 100) == 50


@pytest.mark.parametrize("name,cat", [
    ("Spaghetti n.5", "pasta e riso"), ("Caffè macinato", "colazione"), ("Passata di pomodoro", "dispensa"),
    ("Petto di pollo", "carne"), ("Gin London Dry", "vino e alcolici"), ("Olio originale", "dispensa"),
    ("Coca Cola", "bevande"), ("Cioccolato fondente", "dolci e snack"), ("Prodotto misterioso", "altro"),
])
def test_categorize(name, cat):
    assert categorize(name) == cat


def test_coerce_category():
    assert coerce_category("carne", "qualsiasi") == "carne"
    assert coerce_category("inventata", "Mele golden") == "frutta e verdura"
    assert coerce_category(None, "Latte intero") == "latte e latticini"


def test_parse_validity():
    assert parse_validity("Offerte valide dal 13 al 22 novembre 2026") == (date(2026, 11, 13), date(2026, 11, 22))
    assert parse_validity("DAL 28 OTTOBRE AL 6 NOVEMBRE", date(2026, 10, 20)) == (date(2026, 10, 28), date(2026, 11, 6))
    assert parse_validity("dal 28 dicembre al 6 gennaio", date(2026, 12, 1)) == (date(2026, 12, 28), date(2027, 1, 6))
    assert parse_validity("dal 13/10 al 22/10/2026") == (date(2026, 10, 13), date(2026, 10, 22))
    assert parse_validity("dal 30/12/25 al 5/1") == (date(2025, 12, 30), date(2026, 1, 5))
    assert parse_validity("dal 31 al 32 ottobre 2026") == (None, None)
    assert parse_validity("dal 20 al 10 ottobre 2026") == (None, None)
    assert parse_validity("nessuna data") == (None, None)


def test_similarity():
    assert similarity("Mele Golden", "MELE GOLDEN") == 1.0
    assert similarity("Spaghetti di grano duro", "SPAGHETTI GRANO DURO 500G") > 0.7
    assert similarity("Mele", "Detersivo") < 0.5
    assert similarity("", "x") == 0.0


def test_passwords():
    h = hash_password("segretissima")
    assert verify_password("segretissima", h)
    assert not verify_password("sbagliata!", h)
    assert not verify_password("x", "formato-non-valido")
    with pytest.raises(ValueError):
        hash_password("corta")


def test_tokens(session):
    org = Organization(name="Org")
    session.add(org)
    session.flush()
    user = User(organization_id=org.id, email="a@b.it", password_hash=hash_password("password1"))
    session.add(user)
    session.flush()
    raw = issue_token(session, user, ttl_hours=1)
    assert user_for_token(session, raw) is user
    assert user_for_token(session, "falso") is None
    assert user_for_token(session, "") is None
    tok = session.query(ApiToken).one()
    assert tok.token_hash != raw  # nel database c'è solo l'impronta
    tok.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    session.flush()
    assert user_for_token(session, raw) is None
    raw2 = issue_token(session, user, ttl_hours=1)
    user.is_active = False
    session.flush()
    assert user_for_token(session, raw2) is None
    user.is_active = True
    revoke_token(session, raw2)
    session.flush()
    assert user_for_token(session, raw2) is None
