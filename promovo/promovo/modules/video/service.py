"""Collega il motore video ai dati: dal volantino salvato al file MP4."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from ...config import Settings
from ...models import ContentPiece, Flyer, Store
from ..content.service import featured_offers, validity_text
from .render import FORMATS, RenderError, VideoOffer, VideoSpec, probe_duration, render_video

MAX_OFFERS = {"landscape": 40, "portrait": 6, "square": 6}


def build_spec(store: Store, flyer: Flyer, fmt: str = "landscape", scale: float = 1.0,
               max_offers: int | None = None) -> VideoSpec:
    if fmt not in FORMATS:
        raise RenderError(f"Formato sconosciuto: {fmt}. Usa: {', '.join(FORMATS)}")
    limit = max_offers or MAX_OFFERS[fmt]
    # Schermo in negozio: tutte le offerte nell'ordine del volantino. Social: solo quelle di punta.
    offers = list(flyer.offers)[:limit] if fmt == "landscape" else featured_offers(flyer, limit)
    address = ", ".join(x for x in (store.address, store.city) if x)
    return VideoSpec(
        store_name=store.name,
        headline=flyer.title if flyer.title and flyer.title.lower() != store.name.lower()
        else "Le offerte della settimana",
        validity=validity_text(flyer),
        address=address,
        offers=[VideoOffer(o.name if not o.brand or o.brand.lower() in o.name.lower() else f"{o.brand} {o.name}",
                           o.description, o.price_cents, o.old_price_cents, o.discount_percent, o.conditions,
                           o.crop_path or None) for o in offers],
        brand_color=store.brand_color,
        accent_color=store.accent_color,
        format=fmt,
        scale=scale,
        offer_seconds=3.5 if fmt == "landscape" else 3.0,
    )


def render_flyer_video(session: Session, store: Store, flyer: Flyer, settings: Settings, fmt: str = "landscape",
                       scale: float = 1.0) -> ContentPiece:
    spec = build_spec(store, flyer, fmt, scale)
    settings.ensure_dirs()
    out = settings.data_dir / "renders" / f"flyer{flyer.id}_{fmt}.mp4"
    render_video(spec, Path(out))
    duration = probe_duration(out)
    piece = ContentPiece(store_id=store.id, flyer_id=flyer.id, kind="video", title=f"Video {fmt}",
                         file_path=str(out),
                         meta={"format": fmt, "duration": round(duration, 2), "offers": len(spec.offers)})
    session.add(piece)
    session.flush()
    return piece
