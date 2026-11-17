"""Agente "Copywriter": testi per social, WhatsApp e newsletter a partire dalle offerte.

Ogni testo scritto dall'IA passa dal controllo prezzi: se cita un prezzo che non
esiste nel volantino viene scartato e sostituito dal testo a modello.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...llm import AIRefused, AIUnavailable, LLM
from ...models import ContentPiece, Flyer, Offer, Store
from ...money import find_prices, format_eur

log = logging.getLogger("promovo.content")

_GIORNI = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
_MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre",
         "ottobre", "novembre", "dicembre"]

KINDS = ("instagram", "facebook", "whatsapp", "newsletter")


def fmt_date(d: date | None) -> str:
    return f"{d.day} {_MESI[d.month - 1]}" if d else ""


def validity_text(flyer: Flyer) -> str:
    if flyer.valid_from and flyer.valid_to:
        return f"dal {fmt_date(flyer.valid_from)} al {fmt_date(flyer.valid_to)}"
    if flyer.valid_to:
        return f"fino al {fmt_date(flyer.valid_to)}"
    return ""


def offer_line(o: Offer) -> str:
    name = f"{o.brand} {o.name}".strip() if o.brand and o.brand.lower() not in o.name.lower() else o.name
    extra = f" ({o.description})" if o.description else ""
    line = f"{name}{extra} a {format_eur(o.price_cents)}"
    if o.old_price_cents:
        line += f" invece di {format_eur(o.old_price_cents)}"
    if o.discount_percent:
        line += f" (-{o.discount_percent}%)"
    if o.conditions:
        line += f", {o.conditions}"
    return line


def featured_offers(flyer: Flyer, limit: int = 6) -> list[Offer]:
    feat = [o for o in flyer.offers if o.is_featured]
    rest = sorted((o for o in flyer.offers if not o.is_featured),
                  key=lambda o: (-(o.discount_percent or 0), o.price_cents))
    return (feat + rest)[:limit]


class AIContent(BaseModel):
    instagram_caption: str = Field(description="Didascalia Instagram, max 1.500 caratteri, con emoji misurate")
    hashtags: list[str] = Field(description="5-10 hashtag senza il simbolo #")
    facebook_post: str = Field(description="Post Facebook, tono cordiale, max 1.200 caratteri")
    whatsapp_message: str = Field(description="Messaggio WhatsApp ai clienti iscritti, max 700 caratteri")
    newsletter_subject: str = Field(description="Oggetto email, max 80 caratteri")
    newsletter_body: str = Field(description="Testo email in paragrafi, max 2.500 caratteri")


_SYSTEM = (
    "Sei l'agente Copywriter di Promovo e scrivi per un supermercato di quartiere italiano. "
    "Scrivi testi promozionali chiari, calorosi e onesti, in italiano corretto. "
    "Regole tassative: usa SOLO i prodotti e i prezzi forniti, scritti esattamente come dati "
    "(formato '€ 1,99'); non inventare sconti, prodotti, date o servizi; non usare superlativi falsi. "
    "Indica sempre il periodo di validità se fornito. Nel messaggio WhatsApp ricorda in fondo che si può "
    "rispondere STOP per non ricevere più messaggi."
)


@dataclass
class ContentPack:
    texts: dict[str, dict]           # kind -> {"title", "body", "meta"}
    source: str                      # "ai" | "template"
    warnings: list[str] = field(default_factory=list)


def _allowed_prices(offers: list[Offer]) -> set[int]:
    allowed: set[int] = set()
    for o in offers:
        allowed.add(o.price_cents)
        if o.old_price_cents:
            allowed.add(o.old_price_cents)
    return allowed


def prices_ok(text: str, allowed: set[int]) -> bool:
    return all(p in allowed for p in find_prices(text))


def template_pack(store: Store, flyer: Flyer, offers: list[Offer]) -> dict[str, dict]:
    validity = validity_text(flyer)
    when = f" {validity}" if validity else ""
    lines = [offer_line(o) for o in offers]
    bullets = "\n".join(f"• {line}" for line in lines)
    where = ", ".join(x for x in (store.address, store.city) if x)
    ig = (f"🛒 Le offerte di {store.name}{when}!\n\n{bullets}\n\n"
          f"Ti aspettiamo{(' in ' + where) if where else ''}.")
    tags = ["offerte", "spesa", "volantino", "risparmio", "supermercato"]
    if store.city:
        tags.append(store.city.lower().replace(" ", ""))
    fb = (f"Nuovo volantino da {store.name}{when}.\n\nEcco alcune delle offerte:\n{bullets}\n\n"
          f"Vieni a trovarci{(' in ' + where) if where else ''}!")
    wa = (f"Ciao! Sono arrivate le nuove offerte di {store.name}{when}:\n{bullets}\n\n"
          "Rispondi STOP per non ricevere più messaggi.")
    subject = f"Le nuove offerte di {store.name}"[:80]
    body = (f"Ciao,\n\nè uscito il nuovo volantino di {store.name}{when}. Ecco le offerte da non perdere:\n\n"
            f"{bullets}\n\nTi aspettiamo{(' in ' + where) if where else ''}.\n\nLo staff di {store.name}")
    return {
        "instagram": {"title": "Post Instagram", "body": ig, "meta": {"hashtags": tags}},
        "facebook": {"title": "Post Facebook", "body": fb, "meta": {}},
        "whatsapp": {"title": "Messaggio WhatsApp", "body": wa, "meta": {}},
        "newsletter": {"title": subject, "body": body, "meta": {}},
    }


def generate_content(store: Store, flyer: Flyer, llm: LLM | None) -> ContentPack:
    offers = featured_offers(flyer)
    template = template_pack(store, flyer, offers)
    if not offers:
        return ContentPack(texts=template, source="template", warnings=["Nessuna offerta nel volantino."])
    if llm is None:
        return ContentPack(texts=template, source="template")
    facts = "\n".join(f"- {offer_line(o)} [categoria: {o.category}]" for o in offers)
    info = (f"Negozio: {store.name}\nInsegna: {store.banner or '-'}\nIndirizzo: {store.address or '-'}, "
            f"{store.city or '-'}\nServizi: {', '.join(store.services) or '-'}\n"
            f"Validità: {validity_text(flyer) or 'non indicata'}\n\nOfferte da promuovere:\n{facts}")
    try:
        ai = llm.parse(system=_SYSTEM, content=[{"type": "text", "text": info}], schema=AIContent,
                       effort="medium", max_tokens=8000)
    except (AIUnavailable, AIRefused) as exc:
        return ContentPack(texts=template, source="template", warnings=[f"IA non disponibile: {exc}"])

    allowed = _allowed_prices(offers)
    candidates = {
        "instagram": {"title": "Post Instagram", "body": ai.instagram_caption.strip(),
                      "meta": {"hashtags": [h.lstrip("#").strip() for h in ai.hashtags if h.strip()][:10]}},
        "facebook": {"title": "Post Facebook", "body": ai.facebook_post.strip(), "meta": {}},
        "whatsapp": {"title": "Messaggio WhatsApp", "body": ai.whatsapp_message.strip(), "meta": {}},
        "newsletter": {"title": ai.newsletter_subject.strip()[:80] or template["newsletter"]["title"],
                       "body": ai.newsletter_body.strip(), "meta": {}},
    }
    texts: dict[str, dict] = {}
    warnings = []
    for kind, piece in candidates.items():
        if not piece["body"] or not prices_ok(piece["title"] + "\n" + piece["body"], allowed):
            warnings.append(f"Testo {kind} dell'IA scartato (prezzo non presente nel volantino): "
                            "usato il modello standard.")
            texts[kind] = template[kind]
        else:
            texts[kind] = piece
    if "STOP" not in texts["whatsapp"]["body"]:
        texts["whatsapp"]["body"] += "\n\nRispondi STOP per non ricevere più messaggi."
    return ContentPack(texts=texts, source="ai", warnings=warnings)


def save_content(session: Session, store: Store, flyer: Flyer, pack: ContentPack) -> list[ContentPiece]:
    pieces = []
    for kind in KINDS:
        t = pack.texts[kind]
        piece = ContentPiece(store_id=store.id, flyer_id=flyer.id, kind=kind, title=t["title"], body=t["body"],
                             meta={**t.get("meta", {}), "source": pack.source})
        session.add(piece)
        pieces.append(piece)
    session.flush()
    return pieces
