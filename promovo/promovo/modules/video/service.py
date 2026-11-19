"""Collega il motore video ai dati: dal volantino salvato al file MP4."""
from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...config import Settings
from ...models import ContentPiece, Flyer, Offer, Store
from ..catalog import price_snapshot
from ..content.service import featured_offers, validity_text
from .render import FORMATS, Renderer, RenderError, VideoOffer, VideoSpec, probe_duration, render_video

MAX_OFFERS = {"landscape": 40, "portrait": 6, "square": 6}
FORMAT_LABEL = {"landscape": "Video schermo 16:9", "portrait": "Reel 9:16", "square": "Video post 1:1"}


def cut_image(o: Offer, make: bool = True) -> str | None:
    """Il prodotto scontornato dall'agente (BiRefNet), salvato accanto al ritaglio e riusato le volte dopo.
    make=False: solo se è già pronto (per i video lunghi, dove rifarli tutti richiederebbe troppo)."""
    if not o.crop_path or not Path(o.crop_path).exists():
        return None
    crop = Path(o.crop_path)
    done, no = crop.with_name(crop.stem + "_cut.png"), crop.with_name(crop.stem + "_cut.no")
    if done.exists() and done.stat().st_mtime >= crop.stat().st_mtime:
        return str(done)
    if not make or no.exists():
        return None
    from ... import cutout
    if not cutout.available():
        return None
    from PIL import Image
    try:
        with Image.open(crop) as im:
            res = cutout.cut(im, " ".join(x for x in (o.brand, o.name, o.description) if x))
    except Exception:            # lo scontorno è un di più: se non riesce si usa la foto di prima
        res = None
    if res is None:
        no.touch()               # non affidabile per questa foto: non si riprova ogni volta
        return None
    res.save(done)
    return str(done)


def offer_image(o: Offer, cut: bool = True) -> str | None:
    """La foto migliore disponibile: quella caricata da te, poi il prodotto scontornato dall'agente,
    poi la foto ricavata dal volantino, infine il ritaglio del volantino."""
    if o.photo_path and "manuale_" in o.photo_path and Path(o.photo_path).exists():
        return o.photo_path
    c = cut_image(o, make=cut)
    if c:
        return c
    for p in (o.photo_path, o.crop_path):
        if p and Path(p).exists():
            return p
    return None


def to_video_offer(o: Offer, cut: bool = True) -> VideoOffer:
    return VideoOffer(o.name, o.description, o.price_cents, o.old_price_cents, o.discount_percent, o.conditions,
                      offer_image(o, cut), brand=o.brand, unit_price_text=o.unit_price_text)


def whatsapp_link(number: str) -> str:
    digits = re.sub(r"\D", "", number or "")
    if not digits:
        return ""
    if digits.startswith("00"):
        digits = digits[2:]
    elif not digits.startswith("39") or len(digits) <= 10:
        digits = "39" + digits
    return f"https://wa.me/{digits}"


def store_contacts(store: Store) -> tuple[list[str], str, str]:
    """Righe di contatto, link e didascalia del QR code per la scena finale."""
    lines = []
    if store.opening_hours:
        first = next(iter(store.opening_hours.items()))
        lines.append(f"{first[0]} {first[1]}")
    if store.whatsapp:
        lines.append(f"WhatsApp {store.whatsapp}")
    elif store.phone:
        lines.append(f"Tel. {store.phone}")
    if store.website:
        url = store.website if store.website.startswith("http") else "https://" + store.website
        return lines, url, "Scopri tutte le offerte"
    link = whatsapp_link(store.whatsapp)
    return lines, link, "Scrivici su WhatsApp" if link else ""


def week_idea(flyer: Flyer) -> dict:
    """L'idea della settimana scelta dalla redazione per questo volantino (titolo breve, prodotti)."""
    from sqlalchemy.orm import object_session
    s = object_session(flyer)
    if s is None or flyer.id is None:
        return {}
    row = s.scalars(select(ContentPiece).where(ContentPiece.flyer_id == flyer.id, ContentPiece.kind == "instagram")
                    .order_by(ContentPiece.id.desc()).limit(1)).first()
    return dict(row.meta or {}) if row else {}


def build_spec(store: Store, flyer: Flyer, fmt: str = "landscape", scale: float = 1.0,
               max_offers: int | None = None, music: bool | None = None) -> VideoSpec:
    if fmt not in FORMATS:
        raise RenderError(f"Formato sconosciuto: {fmt}. Usa: {', '.join(FORMATS)}")
    limit = max_offers or MAX_OFFERS[fmt]
    # Schermo in negozio: tutte le offerte nell'ordine del volantino. Social: solo quelle di punta.
    offers = list(flyer.offers)[:limit] if fmt == "landscape" else featured_offers(flyer, limit)
    address = ", ".join(x for x in (store.address, store.city) if x)
    contacts, qr, qr_label = store_contacts(store)
    idea = week_idea(flyer)
    default = flyer.title if flyer.title and flyer.title.lower() not in (store.name.lower(), "superstore") \
        and len(flyer.title) > 3 else "Le offerte della settimana"
    # Sui social il video si apre con l'idea della settimana (la stessa dei testi); sugli schermi in
    # negozio resta il titolo del volantino.
    headline = idea.get("headline") if fmt != "landscape" and idea.get("headline") else default
    return VideoSpec(
        store_name=store.name,
        headline=headline,
        idea_headline=headline != default,
        validity=validity_text(flyer),
        address=address,
        offers=[to_video_offer(o, cut=fmt != "landscape") for o in offers],   # 40 offerte: solo quelle già pronte
        brand_color=store.brand_color,
        accent_color=store.accent_color,
        format=fmt,
        scale=scale,
        offer_seconds=3.4 if fmt == "landscape" else 3.0,
        logo_path=store.logo_path or None,
        contact_lines=contacts,
        qr_data=qr,
        qr_label=qr_label,
        music=store.video_music if music is None else music,
    )


def render_flyer_video(session: Session, store: Store, flyer: Flyer, settings: Settings, fmt: str = "landscape",
                       scale: float = 1.0, music: bool | None = None) -> ContentPiece:
    spec = build_spec(store, flyer, fmt, scale, music=music)
    settings.ensure_dirs()
    out = settings.data_dir / "renders" / f"flyer{flyer.id}_{fmt}.mp4"
    render_video(spec, Path(out))
    duration = probe_duration(out)
    # Immagine di anteprima: la prima offerta a schermo, già tutta visibile.
    poster = out.with_suffix(".jpg")
    try:
        r = Renderer(spec)
        r.frame_at(r.scene_starts()[1] + spec.offer_seconds * 0.7).save(poster, quality=85)
    except Exception:  # l'anteprima è un di più: il video resta valido
        poster = None
    # Un solo video per formato e volantino: rigenerarlo sostituisce il precedente.
    for old in session.scalars(select(ContentPiece).where(ContentPiece.flyer_id == flyer.id,
                                                          ContentPiece.kind == "video")).all():
        if (old.meta or {}).get("format") == fmt:
            session.delete(old)
    piece = ContentPiece(store_id=store.id, flyer_id=flyer.id, kind="video", title=FORMAT_LABEL[fmt],
                         file_path=str(out),
                         meta={"format": fmt, "duration": round(duration, 2), "offers": len(spec.offers),
                               "music": spec.music, "poster": str(poster) if poster else "",
                               "prices_at": price_snapshot(flyer)})
    session.add(piece)
    session.flush()
    return piece
