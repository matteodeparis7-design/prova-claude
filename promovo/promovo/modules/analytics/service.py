"""Agente "Analista": importa le vendite di cassa e misura il risultato di ogni offerta.

Il calcolo è deterministico (nessuna IA): vendite nel periodo del volantino
confrontate con lo stesso numero di giorni subito prima.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ...models import Flyer, SaleRecord, Store
from ...money import parse_price
from ...text_utils import normalize, similarity

MATCH_THRESHOLD = 0.8
MAX_ROWS = 200_000

_ALIASES = {
    "day": ("data", "date", "giorno"),
    "product": ("prodotto", "product", "descrizione", "articolo", "nome"),
    "sku": ("sku", "codice", "ean", "code"),
    "quantity": ("quantita", "quantità", "quantity", "qta", "pezzi"),
    "revenue": ("incasso", "revenue", "totale", "importo", "venduto"),
}


class SalesImportError(ValueError):
    pass


@dataclass
class ImportReport:
    imported: int
    skipped: int
    errors: list[str] = field(default_factory=list)
    first_day: date | None = None
    last_day: date | None = None


def _parse_day(value: str) -> date | None:
    v = value.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            continue
    return None


def _parse_qty(value: str) -> float | None:
    v = value.strip().replace(" ", "")
    if not v:
        return None
    if "," in v:
        v = v.replace(".", "").replace(",", ".")
    try:
        q = float(v)
    except ValueError:
        return None
    return q if q >= 0 else None


def import_sales_csv(session: Session, store: Store, data: bytes, replace_period: bool = True) -> ImportReport:
    """Importa un CSV con colonne data, prodotto, quantità, incasso (sku facoltativo)."""
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
    if not text.strip():
        raise SalesImportError("Il file è vuoto.")
    # Il separatore si ricava dall'intestazione: ";" è il più comune nei CSV italiani
    # (la virgola è usata per i decimali).
    first_line = text.lstrip().splitlines()[0]
    delimiter = max((";", "\t", ","), key=lambda d: (first_line.count(d), d == ";"))
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    header = next(reader, None)
    if not header:
        raise SalesImportError("Intestazione mancante.")
    cols: dict[str, int] = {}
    norm_header = [normalize(h) for h in header]
    for key, aliases in _ALIASES.items():
        for i, h in enumerate(norm_header):
            if h in {normalize(a) for a in aliases}:
                cols[key] = i
                break
    missing = [k for k in ("day", "product", "quantity", "revenue") if k not in cols]
    if missing:
        raise SalesImportError("Colonne mancanti: " + ", ".join(missing) +
                               ". Servono: data, prodotto, quantita, incasso.")

    rows: list[SaleRecord] = []
    errors: list[str] = []
    skipped = 0
    for line_no, row in enumerate(reader, start=2):
        if not any(c.strip() for c in row):
            continue
        if len(rows) >= MAX_ROWS:
            raise SalesImportError(f"Troppe righe: massimo {MAX_ROWS} per file.")
        try:
            day = _parse_day(row[cols["day"]])
            product = row[cols["product"]].strip()
            qty = _parse_qty(row[cols["quantity"]])
            revenue = parse_price(row[cols["revenue"]])
        except IndexError:
            day = product = qty = revenue = None  # type: ignore[assignment]
        if day is None or not product or qty is None or revenue is None:
            skipped += 1
            if len(errors) < 20:
                errors.append(f"Riga {line_no} non valida: {';'.join(row)[:120]}")
            continue
        sku = row[cols["sku"]].strip() if "sku" in cols and cols["sku"] < len(row) else ""
        rows.append(SaleRecord(store_id=store.id, day=day, product=product[:300], sku=sku[:60],
                               quantity=qty, revenue_cents=revenue))
    if not rows:
        raise SalesImportError("Nessuna riga valida nel file.")
    first, last = min(r.day for r in rows), max(r.day for r in rows)
    if replace_period:
        # Reimportare lo stesso periodo non deve raddoppiare le vendite.
        session.execute(delete(SaleRecord).where(SaleRecord.store_id == store.id, SaleRecord.day >= first,
                                                 SaleRecord.day <= last))
    session.add_all(rows)
    session.flush()
    return ImportReport(imported=len(rows), skipped=skipped, errors=errors, first_day=first, last_day=last)


@dataclass
class OfferResult:
    offer_id: int
    name: str
    matched_products: list[str]
    qty_during: float
    qty_before: float
    revenue_during_cents: int
    revenue_before_cents: int
    uplift_percent: float | None       # None se prima non c'erano vendite
    margin_during_cents: int | None


def flyer_performance(session: Session, flyer: Flyer) -> dict:
    if not (flyer.valid_from and flyer.valid_to):
        raise SalesImportError("Il volantino non ha date di validità: impossibile misurarne i risultati.")
    days = (flyer.valid_to - flyer.valid_from).days + 1
    before_start = flyer.valid_from - timedelta(days=days)
    records = session.scalars(select(SaleRecord).where(
        SaleRecord.store_id == flyer.store_id, SaleRecord.day >= before_start, SaleRecord.day <= flyer.valid_to,
    )).all()
    products = sorted({r.product for r in records})
    by_product: dict[str, list[SaleRecord]] = {}
    for r in records:
        by_product.setdefault(r.product, []).append(r)

    results: list[OfferResult] = []
    for o in flyer.offers:
        label = f"{o.brand} {o.name}".strip()
        matched = [p for p in products
                   if max(similarity(o.name, p), similarity(label, p)) >= MATCH_THRESHOLD
                   or (normalize(o.name) and normalize(o.name) in normalize(p))]
        qd = qb = 0.0
        rd = rb = 0
        for p in matched:
            for r in by_product[p]:
                if r.day >= flyer.valid_from:
                    qd += r.quantity
                    rd += r.revenue_cents
                else:
                    qb += r.quantity
                    rb += r.revenue_cents
        uplift = round((qd - qb) / qb * 100, 1) if qb > 0 else None
        margin = None
        if o.cost_cents is not None and matched:
            margin = rd - int(round(qd * o.cost_cents))
        results.append(OfferResult(o.id, label, matched, round(qd, 3), round(qb, 3), rd, rb, uplift, margin))

    measured = [r for r in results if r.matched_products]
    with_uplift = [r for r in measured if r.uplift_percent is not None]
    best = sorted(with_uplift, key=lambda r: -r.uplift_percent)[:5]  # type: ignore[operator]
    worst = sorted(with_uplift, key=lambda r: r.uplift_percent)[:5]  # type: ignore[arg-type]
    total_d = sum(r.revenue_during_cents for r in measured)
    total_b = sum(r.revenue_before_cents for r in measured)
    suggestions = []
    for r in best:
        if r.uplift_percent is not None and r.uplift_percent >= 30:
            suggestions.append(f"Ripetere l'offerta su «{r.name}»: vendite +{r.uplift_percent}%.")
    for r in worst:
        if r.uplift_percent is not None and r.uplift_percent <= 5:
            suggestions.append(f"Rivedere «{r.name}»: l'offerta non ha aumentato le vendite "
                               f"({r.uplift_percent:+}%).")
    unmatched = [r.name for r in results if not r.matched_products]
    if unmatched:
        suggestions.append(f"{len(unmatched)} offerte non trovate nei dati di cassa: controllare i nomi "
                           "o aggiungere il codice prodotto.")
    return {
        "flyer_id": flyer.id,
        "period": {"from": flyer.valid_from.isoformat(), "to": flyer.valid_to.isoformat(),
                   "compared_with_from": before_start.isoformat()},
        "offers": [r.__dict__ for r in results],
        "summary": {
            "offers_measured": len(measured), "offers_unmatched": len(unmatched),
            "revenue_during_cents": total_d, "revenue_before_cents": total_b,
            "revenue_change_percent": round((total_d - total_b) / total_b * 100, 1) if total_b else None,
        },
        "best": [r.name for r in best], "worst": [r.name for r in worst],
        "suggestions": suggestions,
    }
