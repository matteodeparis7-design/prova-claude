"""Caricamento di un volantino: salvataggio, estrazione, verifica, ritagli dei prodotti."""
from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session

from ...config import Settings
from ...llm import LLM
from ...models import Flyer, FlyerStatus, Offer, Store
from .extract import extract_offers, pick_featured
from .pdf import InvalidPDF, clean_card, extract_photo, normalize_upload, open_pdf, render_crop

log = logging.getLogger("promovo.flyer")


def create_flyer(session: Session, store: Store, pdf_bytes: bytes, settings: Settings, title: str = "",
                 competitor: str = "") -> Flyer:
    """Valida e salva il PDF; il volantino resta "in lettura". Solleva InvalidPDF se il file non va bene."""
    if len(pdf_bytes) > settings.max_upload_mb * 1024 * 1024:
        raise InvalidPDF(f"Il file supera {settings.max_upload_mb} MB.")
    pdf_bytes = normalize_upload(pdf_bytes)   # anche JPG, PNG e WEBP
    doc = open_pdf(pdf_bytes)  # valida prima di salvare
    page_count = doc.page_count
    doc.close()
    settings.ensure_dirs()
    flyer = Flyer(store_id=store.id, title=title, pdf_path="", pdf_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
                  page_count=page_count, status=FlyerStatus.processing, competitor=competitor.strip()[:120])
    session.add(flyer)
    session.flush()
    # Un file per volantino: cancellarne uno non tocca gli altri.
    pdf_path = settings.data_dir / "flyers" / f"{flyer.id}.pdf"
    pdf_path.write_bytes(pdf_bytes)
    flyer.pdf_path = str(pdf_path)
    session.flush()
    return flyer


def process_flyer(session: Session, flyer: Flyer, settings: Settings, llm: LLM | None,
                  today: date | None = None, progress: Callable[[int, int], None] | None = None) -> Flyer:
    """Legge le offerte di un volantino già salvato. In caso di errore il volantino resta senza offerte."""
    try:
        doc = open_pdf(Path(flyer.pdf_path).read_bytes())
    except (OSError, InvalidPDF) as exc:
        flyer.status, flyer.error = FlyerStatus.failed, f"PDF non leggibile: {exc}"
        session.flush()
        return flyer
    try:
        result = extract_offers(doc, llm, today, progress)
        featured = pick_featured(result.offers)
        crops_dir = settings.data_dir / "crops" / str(flyer.id)
        offers = []
        for idx, raw in enumerate(result.offers):
            crop = render_crop(doc[raw.page - 1], raw.bbox, crops_dir / f"{idx:03d}.png")
            photo = ""
            if raw.photo_bbox:
                photo = str(extract_photo(doc[raw.page - 1], raw.photo_bbox, crops_dir / f"{idx:03d}_foto.png"))
            elif raw.erase:
                cleaned = clean_card(doc[raw.page - 1], raw.bbox, raw.erase, crops_dir / f"{idx:03d}_foto.png")
                photo = str(cleaned) if cleaned else ""
            offers.append(Offer(
                flyer_id=flyer.id, position=idx, page=raw.page, name=raw.name, brand=raw.brand,
                description=raw.description, category=raw.category, price_cents=raw.price_cents,
                old_price_cents=raw.old_price_cents, discount_percent=raw.discount_percent,
                unit_price_text=raw.unit_price_text, conditions=raw.conditions, bbox=raw.bbox,
                crop_path=str(crop), price_verified=raw.price_verified, verified_by=raw.verified_by,
                photo_bbox=raw.photo_bbox or [], photo_path=photo,
                is_featured=idx in featured,
            ))
        # Le offerte si salvano tutte insieme, solo se la lettura è andata a buon fine.
        session.add_all(offers)
        flyer.extraction_method = result.method
        flyer.title = flyer.title or result.title
        flyer.valid_from, flyer.valid_to = result.valid_from, result.valid_to
        flyer.warnings = result.warnings
        flyer.error = ""
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


def ingest_flyer(session: Session, store: Store, pdf_bytes: bytes, settings: Settings, llm: LLM | None,
                 title: str = "", today: date | None = None) -> Flyer:
    """Salva e legge subito il volantino (usato da script e test)."""
    return process_flyer(session, create_flyer(session, store, pdf_bytes, settings, title), settings, llm, today)


def delete_flyer_files(flyer: Flyer, settings: Settings) -> None:
    crops_dir = settings.data_dir / "crops" / str(flyer.id)
    if crops_dir.exists():
        for f in crops_dir.iterdir():
            f.unlink(missing_ok=True)
        crops_dir.rmdir()
    # Video e grafiche generati per questo volantino.
    renders = settings.data_dir / "renders"
    if renders.exists():
        for f in renders.glob(f"flyer{flyer.id}_*"):
            f.unlink(missing_ok=True)
    if flyer.pdf_path:
        Path(flyer.pdf_path).unlink(missing_ok=True)


def replicate_flyer(session: Session, flyer: Flyer, target: Store, settings: Settings) -> Flyer:
    """Lo stesso volantino per un altro punto vendita della catena: offerte, prezzi già controllati e
    ritagli vengono copiati (niente seconda lettura); i materiali poi si creano con i dati del negozio."""
    import shutil
    settings.ensure_dirs()
    copy = Flyer(store_id=target.id, title=flyer.title, pdf_path="", pdf_sha256=flyer.pdf_sha256,
                 page_count=flyer.page_count, valid_from=flyer.valid_from, valid_to=flyer.valid_to,
                 status=FlyerStatus.ready, extraction_method=flyer.extraction_method, error="",
                 warnings=list(flyer.warnings or []), competitor="")
    session.add(copy)
    session.flush()
    pdf_path = settings.data_dir / "flyers" / f"{copy.id}.pdf"
    if flyer.pdf_path and Path(flyer.pdf_path).exists():
        shutil.copyfile(flyer.pdf_path, pdf_path)
    copy.pdf_path = str(pdf_path)
    dst_dir = settings.data_dir / "crops" / str(copy.id)
    dst_dir.mkdir(parents=True, exist_ok=True)

    def moved(path: str) -> str:
        if not path or not Path(path).exists():
            return ""
        dst = dst_dir / Path(path).name
        shutil.copyfile(path, dst)
        return str(dst)
    for o in flyer.offers:
        session.add(Offer(
            flyer_id=copy.id, position=o.position, page=o.page, name=o.name, brand=o.brand,
            description=o.description, category=o.category, price_cents=o.price_cents,
            old_price_cents=o.old_price_cents, discount_percent=o.discount_percent,
            unit_price_text=o.unit_price_text, conditions=o.conditions, bbox=list(o.bbox or []),
            crop_path=moved(o.crop_path), photo_bbox=list(o.photo_bbox or []), photo_path=moved(o.photo_path),
            manual=o.manual, price_verified=o.price_verified, verified_by=o.verified_by,
            is_featured=o.is_featured, cost_cents=o.cost_cents))
    session.flush()
    session.refresh(copy)
    return copy
