"""Caricamento di un volantino: salvataggio, estrazione, verifica, ritagli dei prodotti."""
from __future__ import annotations

import hashlib
import logging
from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session

from ...config import Settings
from ...llm import LLM
from ...models import Flyer, FlyerStatus, Offer, Store
from .extract import extract_offers, pick_featured
from .pdf import InvalidPDF, open_pdf, render_crop

log = logging.getLogger("promovo.flyer")


def ingest_flyer(session: Session, store: Store, pdf_bytes: bytes, settings: Settings, llm: LLM | None,
                 title: str = "", today: date | None = None) -> Flyer:
    """Salva il PDF, estrae le offerte e crea il volantino. Solleva InvalidPDF se il file non va bene."""
    if len(pdf_bytes) > settings.max_upload_mb * 1024 * 1024:
        raise InvalidPDF(f"Il file supera {settings.max_upload_mb} MB.")
    doc = open_pdf(pdf_bytes)  # valida prima di salvare
    settings.ensure_dirs()
    sha = hashlib.sha256(pdf_bytes).hexdigest()
    flyer = Flyer(store_id=store.id, title=title, pdf_path="", pdf_sha256=sha,
                  page_count=doc.page_count, status=FlyerStatus.processing)
    session.add(flyer)
    session.flush()
    # Un file per volantino: cancellarne uno non tocca gli altri.
    pdf_path = settings.data_dir / "flyers" / f"{flyer.id}.pdf"
    pdf_path.write_bytes(pdf_bytes)
    flyer.pdf_path = str(pdf_path)

    try:
        result = extract_offers(doc, llm, today)
        flyer.extraction_method = result.method
        flyer.title = title or result.title
        flyer.valid_from, flyer.valid_to = result.valid_from, result.valid_to
        featured = pick_featured(result.offers)
        crops_dir = settings.data_dir / "crops" / str(flyer.id)
        for idx, raw in enumerate(result.offers):
            crop = render_crop(doc[raw.page - 1], raw.bbox, crops_dir / f"{idx:03d}.png")
            session.add(Offer(
                flyer_id=flyer.id, position=idx, page=raw.page, name=raw.name, brand=raw.brand,
                description=raw.description, category=raw.category, price_cents=raw.price_cents,
                old_price_cents=raw.old_price_cents, discount_percent=raw.discount_percent,
                unit_price_text=raw.unit_price_text, conditions=raw.conditions, bbox=raw.bbox,
                crop_path=str(crop), price_verified=raw.price_verified, is_featured=idx in featured,
            ))
        flyer.warnings = result.warnings
        flyer.status = FlyerStatus.ready
    except Exception as exc:
        log.exception("Estrazione del volantino %s fallita", flyer.id)
        flyer.status = FlyerStatus.failed
        flyer.error = str(exc)[:2000]
    finally:
        doc.close()
    session.flush()
    session.refresh(flyer)
    return flyer


def delete_flyer_files(flyer: Flyer, settings: Settings) -> None:
    crops_dir = settings.data_dir / "crops" / str(flyer.id)
    if crops_dir.exists():
        for f in crops_dir.iterdir():
            f.unlink(missing_ok=True)
        crops_dir.rmdir()
    Path(flyer.pdf_path).unlink(missing_ok=True)
