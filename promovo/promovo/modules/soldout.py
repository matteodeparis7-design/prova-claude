"""«Esaurito»: contenuti che sanno cosa c'è a scaffale.

Come gli annunci online che si fermano quando il prodotto finisce (Google Shopping, e-commerce), portato nel negozio:
il punto vendita segna «esaurito» con un tocco e quel prodotto esce dai materiali nuovi del negozio (grafiche,
video per gli schermi e per i social, testi, locandina). Promovo dice quali materiali già fatti lo mostrano ancora, e
se il negozio vuole prepara il messaggio per i clienti («esaurito, grazie!»). Per le catene la sede vede in quali
punti vendita e dopo quanti giorni le offerte finiscono: un segnale per gli ordini e per i prossimi volantini.

Un prodotto in offerta che manca a scaffale delude il cliente più del solito (GS1 Italia / ECR): meglio dirlo prima.
"""
from __future__ import annotations

from datetime import datetime, timezone

from PIL import Image, ImageDraw
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ContentPiece, Flyer, Offer, Store
from .video.render import (INK, WHITE, fit_text, font, hex_rgb, logo_image, mix, pill, product_visual,
                           readable_on_paper, soft_background, text_layer)
from .video.service import offer_image

KIND_LABEL = {"image": "grafica", "video": "video", "instagram": "post Instagram", "facebook": "post Facebook",
              "reel": "didascalia Reel", "plan": "piano"}


def mark(o: Offer, sold_out: bool, note: str = "") -> Offer:
    if sold_out:
        o.sold_out_at = o.sold_out_at or datetime.now(timezone.utc)
        o.sold_out_note = " ".join((note or "").split())[:120]
    else:
        o.sold_out_at = None
        o.sold_out_note = ""
    return o


def _shows(p: ContentPiece, o: Offer) -> bool:
    ids = (p.meta or {}).get("offer_ids")
    if ids is not None:
        return o.id in ids
    if p.kind in ("instagram", "facebook", "reel", "plan"):
        return o.name.lower() in (p.body or "").lower()
    return p.kind in ("image", "video")           # materiali vecchi senza elenco: per prudenza sì


def stale_pieces(session: Session, flyer: Flyer) -> list[dict]:
    """I materiali fatti prima che un prodotto finisse e che lo mostrano ancora."""
    gone = [o for o in flyer.offers if o.sold_out_at is not None]
    if not gone:
        return []
    out = []
    for p in session.scalars(select(ContentPiece).where(ContentPiece.flyer_id == flyer.id)):
        created = p.created_at if p.created_at.tzinfo else p.created_at.replace(tzinfo=timezone.utc)
        hit = [o for o in gone if _shows(p, o) and created < (o.sold_out_at if o.sold_out_at.tzinfo else
                                                                 o.sold_out_at.replace(tzinfo=timezone.utc))]
        if hit:
            out.append({"piece_id": p.id, "kind": p.kind, "title": p.title or KIND_LABEL.get(p.kind, p.kind),
                        "offers": [o.name for o in hit]})
    return out


def remake_items(stale: list[dict], pieces: list[ContentPiece]) -> list[str]:
    """Cosa rifare con il pacchetto (testi, immagini, i formati video coinvolti)."""
    by_id = {p.id: p for p in pieces}
    items = set()
    for s in stale:
        p = by_id.get(s["piece_id"])
        if p is None:
            continue
        if p.kind == "image":
            items.add("images")
        elif p.kind == "video":
            items.add({"landscape": "video_landscape", "portrait": "video_portrait",
                       "square": "video_square"}.get((p.meta or {}).get("format"), "video_landscape"))
        elif p.kind in ("instagram", "facebook", "reel", "plan"):
            items.add("texts")
    order = ["texts", "images", "video_portrait", "video_square", "video_landscape"]
    return [i for i in order if i in items]


# ----------------------------------------------------------------- il messaggio facoltativo per i clienti

def message_text(store: Store, o: Offer) -> str:
    tone = store.tone or "familiare"
    emoji = tone in ("familiare", "giovane")
    name = " ".join(x for x in (o.brand, o.name) if x)
    lines = [(("🙏 " if emoji else "") + f"{name}: esaurito!").strip(),
             f"L'offerta è andata a ruba: grazie a tutti." if tone != "elegante" else "L'offerta è terminata: grazie."]
    if o.sold_out_note:
        lines.append(o.sold_out_note.rstrip(".") + ".")
    lines.append("Le altre offerte del volantino continuano.")
    return " ".join(lines)


def message_image(store: Store, o: Offer) -> Image.Image:
    W, H = 1080, 1350
    brand = hex_rgb(store.brand_color)
    img = soft_background(W, H, brand, 1.0)
    d = ImageDraw.Draw(img)
    pad = 70
    logo = logo_image(store.logo_path or None, 300, 96, (250, 247, 240))
    if logo is not None:
        img.alpha_composite(logo, ((W - logo.width) // 2, 60))
    else:
        fs, ls = fit_text(store.name, W - 2 * pad, 60, 42, True, 1)
        d.text((W // 2, 100), ls[0], font=fs, fill=readable_on_paper(brand), anchor="mm")
    vis = product_visual(offer_image(o, cut=True), W - 2 * pad, 470, brand, 1.0, o.name)
    vis = vis.convert("LA").convert("RGBA")                          # in grigio: il prodotto non c'è più
    img.alpha_composite(vis, (pad, 200))
    stamp = pill("ESAURITO", 92, (190, 30, 40))
    stamp = stamp.rotate(8, expand=True, resample=Image.BICUBIC)
    img.alpha_composite(stamp, ((W - stamp.width) // 2, 200 + 470 // 2 - stamp.height // 2))
    y = 720
    fn, ln = fit_text(" ".join(x for x in (o.brand, o.name) if x), W - 2 * pad, 140, 64, True, 2, min_size=36)
    nl = text_layer(ln, fn, INK, "center")
    img.alpha_composite(nl, ((W - nl.width) // 2, y))
    y += nl.height + 30
    ft, lt = fit_text("Grazie a tutti!", W - 2 * pad, 120, 96, "display", 1)
    tl = text_layer(lt, ft, readable_on_paper(brand), "center")
    img.alpha_composite(tl, ((W - tl.width) // 2, y))
    y += tl.height + 24
    if o.sold_out_note:
        fm, lm = fit_text(o.sold_out_note, W - 2 * pad, 110, 46, True, 2)
        ml = text_layer(lm, fm, INK, "center")
        img.alpha_composite(ml, ((W - ml.width) // 2, y))
    d.text((W // 2, H - 70), "Le altre offerte del volantino continuano", font=font(32, True),
           fill=mix(INK, WHITE, 0.25), anchor="mm")
    return img.convert("RGB")


# ----------------------------------------------------------------- il quadro per la sede

def network(session: Session, organization_id: int) -> list[dict]:
    """In quali punti vendita e dopo quanti giorni sono finiti i prodotti dei volantini in corso."""
    stores = {s.id: s for s in session.scalars(select(Store).where(Store.organization_id == organization_id))}
    rows = session.scalars(select(Offer).join(Flyer, Offer.flyer_id == Flyer.id)
                           .where(Flyer.store_id.in_(list(stores)), Flyer.competitor == "",
                                  Offer.sold_out_at.is_not(None))).all()
    out = []
    for o in rows:
        f = o.flyer
        start = f.valid_from
        when = o.sold_out_at if o.sold_out_at.tzinfo else o.sold_out_at.replace(tzinfo=timezone.utc)
        days = (when.date() - start).days + 1 if start else None
        out.append({"offer": " ".join(x for x in (o.brand, o.name, o.description) if x), "store": stores[f.store_id].name,
                    "store_id": f.store_id, "flyer_id": f.id, "sold_out_at": when.isoformat(), "day_of_flyer": days})
    out.sort(key=lambda r: (r["offer"].lower(), r["sold_out_at"]))
    return out
