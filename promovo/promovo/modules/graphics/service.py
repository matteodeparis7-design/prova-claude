"""Agente "Grafico": immagini pronte per i social, con lo stesso stile dei video.

- copertina 1080x1350 (post Instagram/Facebook) con le 4 offerte di punta;
- storia 1080x1920 (Storie e stati WhatsApp) con 6 offerte;
- un'immagine 1080x1080 per ogni offerta in evidenza.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...config import Settings
from ...models import ContentPiece, Flyer, Store
from ..content.service import featured_offers, validity_text
from ..video.render import (
    INK, PAPER, WHITE, Renderer, VideoOffer, brand_background, discount_burst, fit_text, hex_rgb,
    logo_image, mix, old_price_line, paste, pill, price_block, product_visual, readable_on_paper,
    scaled, soft_background, text_layer, text_on,
)
from ..video.service import build_spec, to_video_offer

FORMATS = {"cover": (1080, 1350), "story": (1080, 1920), "offer": (1080, 1080), "idea": (1080, 1350)}
LABELS = {"cover": "Post copertina", "story": "Storia", "offer": "Post offerta", "idea": "Post idea della settimana"}
# Idee che hanno senso come grafica a sé (più prodotti insieme o una ricorrenza)
IDEA_KINDS = {"combo", "occasion", "under_euro", "fresh", "stock", "weekend", "basket"}


def _card(o: VideoOffer, w: int, h: int, brand, accent, u: float) -> Image.Image:
    """Riquadro di un'offerta per le griglie: foto, nome, prezzo, sconto."""
    card = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(card)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=int(34 * u), fill=WHITE + (255,))
    pad = int(22 * u)
    img_h = int(h * 0.47)
    prod = product_visual(o.image_path, w - 2 * pad, img_h, brand, u * 0.6, o.name)
    card.alpha_composite(prod, (pad, pad))
    y = pad + img_h + int(6 * u)
    fn, ln = fit_text(o.name, w - 2 * pad, int(h * 0.15), int(34 * u), True, 2, min_size=int(18 * u))
    name = text_layer(ln, fn, INK)
    card.alpha_composite(name, (pad, y))
    y += name.height + int(4 * u)
    price = price_block(o.price_cents, int(h * 0.22), brand)      # il prezzo è ciò che vende: ben visibile
    if price.width > w - 2 * pad:
        price = scaled(price, (w - 2 * pad) / price.width)
    py = h - pad - price.height
    if o.description:
        fd, ld = fit_text(o.description, w - 2 * pad, int(34 * u), int(26 * u), False, 1)
        desc = text_layer(ld, fd, (100, 104, 116))
        if y + desc.height <= py - int(6 * u):      # solo se non tocca il prezzo
            card.alpha_composite(desc, (pad, y))
    card.alpha_composite(price, (pad, py))
    if o.old_price_cents:
        old = old_price_line(o.old_price_cents, int(28 * u), (110, 112, 120))
        if pad + price.width + int(14 * u) + old.width <= w - pad:
            card.alpha_composite(old, (pad + price.width + int(14 * u), py + price.height - old.height - int(4 * u)))
    if o.discount_percent:
        burst = discount_burst(o.discount_percent, int(min(w, h) * 0.3), accent)
        card.alpha_composite(burst, (w - burst.width - int(8 * u), int(8 * u)))
    return card


def _shadowed(card: Image.Image, u: float) -> Image.Image:
    from ..video.render import shadow_of
    sh = shadow_of(card, 16 * u, 0.18)
    out = Image.new("RGBA", sh.size, (0, 0, 0, 0))
    out.alpha_composite(sh, (0, int(10 * u)))
    out.alpha_composite(card, ((sh.width - card.width) // 2, (sh.height - card.height) // 2))
    return out


def grid_image(store: Store, flyer: Flyer, kind: str) -> Image.Image:
    """Copertina (2x2) o storia (2x3) con le offerte di punta."""
    W, H = FORMATS[kind]
    u = W / 1080
    brand, accent = hex_rgb(store.brand_color), hex_rgb(store.accent_color)
    n = 4 if kind == "cover" else 6
    offers = [to_video_offer(o) for o in featured_offers(flyer, n)]
    img = soft_background(W, H, brand, u)
    d = ImageDraw.Draw(img)
    head_h = int((300 if kind == "cover" else 380) * u)
    head = brand_background(W, head_h, brand, accent, u)
    img.alpha_composite(head, (0, 0))
    fg = text_on(brand)
    x, y = int(56 * u), int(44 * u)
    logo = logo_image(store.logo_path or None, int(300 * u), int(96 * u), brand)
    if logo is not None:
        img.alpha_composite(logo, (x, y))
        y += logo.height + int(18 * u)
    title = "Le offerte della settimana"
    ft, lt = fit_text(title, W - 2 * x, int(80 * u), int(66 * u), "display", 1)
    d.text((x, y), lt[0], font=ft, fill=fg)
    y += int(ft.size * 1.2)
    sub = store.name + (f" · {validity_text(flyer)}" if validity_text(flyer) else "")
    fs, ls = fit_text(sub, W - 2 * x, int(44 * u), int(32 * u), False, 1)
    d.text((x, y), ls[0], font=fs, fill=fg)

    cols, rows = 2, (2 if kind == "cover" else 3)
    gap = int(28 * u)
    top = head_h + gap
    bottom = H - int(78 * u)
    cw = (W - 2 * int(44 * u) - gap) // cols
    ch = (bottom - top - gap * (rows - 1)) // rows
    for i, o in enumerate(offers[: cols * rows]):
        c, r = i % cols, i // cols
        card = _shadowed(_card(o, cw, ch, brand, accent, u), u)
        cx = int(44 * u) + c * (cw + gap) + cw // 2
        cy = top + r * (ch + gap) + ch // 2
        paste(img, card, cx - card.width / 2, cy - card.height / 2)
    note = "Offerte valide fino a esaurimento scorte"
    if store.address or store.city:
        note = ", ".join(x for x in (store.address, store.city) if x) + " · " + note
    fn, ln = fit_text(note, W - 2 * int(44 * u), int(40 * u), int(26 * u), False, 1)
    d.text((W / 2, H - int(40 * u)), ln[0], font=fn, fill=readable_on_paper(brand), anchor="mm")
    return img.convert("RGB")


def idea_image(store: Store, flyer: Flyer, idea: dict) -> Image.Image | None:
    """La grafica dell'idea della settimana: titolo grande, i prodotti dell'idea, dove e fino a quando.
    Cambia ogni settimana perché cambia l'idea (cena completa, ricorrenza, reparto, scorta...)."""
    if idea.get("angle") not in IDEA_KINDS or not idea.get("headline"):
        return None
    by_id = {o.id: o for o in flyer.offers}
    items = [by_id[i] for i in idea.get("featured_ids") or [] if i in by_id][:4]
    if len(items) < 2:
        return None
    W, H = FORMATS["idea"]
    u = W / 1080
    brand, accent = hex_rgb(store.brand_color), hex_rgb(store.accent_color)
    img = soft_background(W, H, brand, u)
    d = ImageDraw.Draw(img)
    pad = int(64 * u)
    # testata: logo e periodo
    y = int(56 * u)
    logo = logo_image(store.logo_path or None, int(260 * u), int(84 * u), PAPER)
    if logo is not None:
        img.alpha_composite(logo, (pad, y))
    vt = validity_text(flyer)
    if vt:
        fv, lv = fit_text(vt.capitalize(), int(420 * u), int(40 * u), int(30 * u), True, 1)
        d.text((W - pad, y + int(42 * u)), lv[0], font=fv, fill=readable_on_paper(brand), anchor="rm")
    y += int(130 * u)
    # occhiello e titolo
    fe, le = fit_text("QUESTA SETTIMANA", W - 2 * pad, int(40 * u), int(30 * u), True, 1)
    d.text((pad, y), le[0], font=fe, fill=readable_on_paper(brand))
    y += int(52 * u)
    fh, lh = fit_text(idea["headline"], W - 2 * pad, int(260 * u), int(118 * u), "display", 2, min_size=int(60 * u))
    for ln in lh:
        d.text((pad, y), ln, font=fh, fill=INK)
        y += int(fh.size * 1.12)
    if idea.get("headline_sub"):
        fs, ls = fit_text(idea["headline_sub"], W - 2 * pad, int(50 * u), int(38 * u), False, 1)
        d.text((pad, y + int(6 * u)), ls[0], font=fs, fill=(96, 100, 112))
        y += int(64 * u)
    # i prodotti dell'idea
    top, bottom = y + int(30 * u), H - int(120 * u)
    gap = int(26 * u)
    n = len(items)
    cols, rows = (n, 1) if n <= 3 else (2, 2)
    cw = (W - 2 * pad - gap * (cols - 1)) // cols
    ch = min((bottom - top - gap * (rows - 1)) // rows, int(cw * ((1.8 if n == 3 else 1.45) if rows == 1 else 1.12)))
    grid_h = rows * ch + (rows - 1) * gap
    top += max(0, (bottom - top - grid_h) // 2)
    for i, o in enumerate(items):
        c, r = i % cols, i // cols
        card = _shadowed(_card(to_video_offer(o), cw, ch, brand, accent, u), u)
        cx = pad + c * (cw + gap) + cw // 2
        cy = top + r * (ch + gap) + ch // 2
        paste(img, card, cx - card.width / 2, cy - card.height / 2)
    # piede: dove
    where = ", ".join(x for x in (store.address, store.city) if x) or store.name
    band = Image.new("RGBA", (W, int(96 * u)), brand + (255,))
    img.alpha_composite(band, (0, H - band.height))
    ff, lf = fit_text(f"{store.name} · {where}" if where != store.name else store.name, W - 2 * pad,
                      int(50 * u), int(34 * u), True, 1)
    d.text((W / 2, H - band.height / 2), lf[0], font=ff, fill=text_on(brand), anchor="mm")
    return img.convert("RGB")


def offer_image(store: Store, flyer: Flyer, offer_index: int) -> Image.Image:
    """Immagine quadrata di una sola offerta: lo stesso fotogramma finale del video."""
    spec = build_spec(store, flyer, "square", music=False)
    feats = featured_offers(flyer, 6)
    spec.offers = [to_video_offer(feats[offer_index])]
    spec.footer_note = "Offerte valide fino a esaurimento scorte."
    r = Renderer(spec)
    draw, n, _ = r.scenes[1]
    return draw(0.85).convert("RGB")


def render_flyer_images(session: Session, store: Store, flyer: Flyer, settings: Settings) -> list[ContentPiece]:
    if not flyer.offers:
        return []
    settings.ensure_dirs()
    out_dir = settings.data_dir / "renders"
    # Rigenerare sostituisce le immagini precedenti di questo volantino.
    for old in session.scalars(select(ContentPiece).where(ContentPiece.flyer_id == flyer.id,
                                                          ContentPiece.kind == "image")).all():
        if old.file_path:
            Path(old.file_path).unlink(missing_ok=True)
        session.delete(old)
    pieces = []
    from ..video.service import week_idea
    idea = week_idea(flyer)
    jobs = [("idea", None), ("cover", None), ("story", None)] + [("offer", i) for i in range(min(6, len(flyer.offers)))]
    for kind, idx in jobs:
        if kind == "idea":
            img = idea_image(store, flyer, idea)
            if img is None:
                continue
        else:
            img = grid_image(store, flyer, kind) if idx is None else offer_image(store, flyer, idx)
        name = f"flyer{flyer.id}_img_{kind}{'' if idx is None else f'_{idx + 1}'}.jpg"
        path = out_dir / name
        img.save(path, format="JPEG", quality=92, optimize=True)
        title = LABELS[kind] + ("" if idx is None else f" {idx + 1}")
        piece = ContentPiece(store_id=store.id, flyer_id=flyer.id, kind="image", title=title, file_path=str(path),
                             meta={"format": kind, "width": img.width, "height": img.height})
        session.add(piece)
        pieces.append(piece)
    session.flush()
    return pieces


__all__ = ["render_flyer_images", "grid_image", "offer_image", "FORMATS", "PAPER", "mix", "pill"]


def render_idea_image(session: Session, store: Store, flyer: Flyer, settings: Settings) -> ContentPiece | None:
    """Rifà solo la grafica dell'idea della settimana (dopo «Un'altra idea»)."""
    from ..video.service import week_idea
    for old in session.scalars(select(ContentPiece).where(ContentPiece.flyer_id == flyer.id,
                                                          ContentPiece.kind == "image")).all():
        if (old.meta or {}).get("format") == "idea":
            if old.file_path:
                Path(old.file_path).unlink(missing_ok=True)
            session.delete(old)
    session.flush()
    img = idea_image(store, flyer, week_idea(flyer))
    if img is None:
        return None
    settings.ensure_dirs()
    path = settings.data_dir / "renders" / f"flyer{flyer.id}_img_idea.jpg"
    img.save(path, format="JPEG", quality=92, optimize=True)
    piece = ContentPiece(store_id=store.id, flyer_id=flyer.id, kind="image", title=LABELS["idea"], file_path=str(path),
                         meta={"format": "idea", "width": img.width, "height": img.height})
    session.add(piece)
    session.flush()
    return piece
