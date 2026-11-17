"""Gestione precisa degli importi in euro (sempre in centesimi interi)."""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

# Riconosce prezzi come "1,99", "€ 1,99", "1.99€", "12,90", "1.299,00".
PRICE_RE = re.compile(r"(?<![\d.,])(\d{1,3}(?:\.\d{3})+|\d{1,5})[,.](\d{2})(?!\d)")


def parse_price(text: str | int | float | None) -> int | None:
    """Converte un prezzo scritto all'italiana (o un numero) in centesimi. None se non valido."""
    if text is None:
        return None
    if isinstance(text, bool):
        return None
    if isinstance(text, int):
        return text * 100 if text >= 0 else None
    if isinstance(text, float):
        try:
            d = Decimal(str(text))
        except InvalidOperation:
            return None
        return int((d * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)) if d >= 0 else None
    s = str(text).strip().replace("€", "").replace("EUR", "").replace(" ", " ").strip()
    if not s:
        return None
    m = PRICE_RE.search(s)
    if m:
        euros = int(m.group(1).replace(".", ""))
        return euros * 100 + int(m.group(2))
    if re.fullmatch(r"\d{1,5}", s):
        return int(s) * 100
    return None


def find_prices(text: str) -> list[int]:
    """Tutti i prezzi (in centesimi) che compaiono in un testo."""
    out = []
    for m in PRICE_RE.finditer(text.replace(" ", " ")):
        out.append(int(m.group(1).replace(".", "")) * 100 + int(m.group(2)))
    return out


def format_eur(cents: int | None) -> str:
    """12345 -> '€ 123,45'."""
    if cents is None:
        return ""
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    euros, rest = divmod(cents, 100)
    euros_txt = f"{euros:,}".replace(",", ".")
    return f"{sign}€ {euros_txt},{rest:02d}"


def price_parts(cents: int) -> tuple[str, str]:
    """12345 -> ('123', '45') per il disegno dei cartellini."""
    euros, rest = divmod(abs(cents), 100)
    return f"{euros:,}".replace(",", "."), f"{rest:02d}"


def discount_percent(price_cents: int, old_price_cents: int | None) -> int | None:
    if not old_price_cents or old_price_cents <= price_cents or price_cents < 0:
        return None
    pct = (Decimal(old_price_cents - price_cents) * 100 / Decimal(old_price_cents))
    return int(pct.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
