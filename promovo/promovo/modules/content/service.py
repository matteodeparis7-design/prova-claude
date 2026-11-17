"""Agente "Copywriter": testi per social, WhatsApp e newsletter a partire dalle offerte.

Ogni testo scritto dall'IA passa dal controllo prezzi: se cita un prezzo che non
esiste nel volantino viene scartato e sostituito dal testo a modello.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date

from pydantic import BaseModel, Field
from sqlalchemy import select
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
    vf, vt = flyer.valid_from, flyer.valid_to
    if vf and vt:
        if (vf.month, vf.year) == (vt.month, vt.year):
            return f"dal {vf.day} al {fmt_date(vt)}"           # dal 13 al 22 novembre
        return f"dal {fmt_date(vf)} al {fmt_date(vt)}"
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
    "Sei l'agente Copywriter di Promovo: scrivi la comunicazione settimanale di un supermercato italiano, "
    "come farebbe un bravo social media manager locale. Italiano impeccabile, frasi brevi, ritmo.\n"
    "Regole tassative:\n"
    "- Usa SOLO prodotti e prezzi forniti, scritti esattamente nel formato dato (es. '€ 1,99'). "
    "Non inventare sconti, prodotti, date, servizi o promesse; niente superlativi falsi.\n"
    "- Apri con una frase d'attacco concreta, costruita sull'offerta più forte.\n"
    "- Rispetta il tono di voce indicato: familiare (caldo, vicino, emoji misurate), elegante (sobrio, "
    "niente emoji), giovane (energico, emoji), essenziale (asciutto, elenchi).\n"
    "- Instagram: elenco leggibile, una emoji pertinente per riga se il tono lo consente, invito finale.\n"
    "- WhatsApp: corto, prezzi in *grassetto* con gli asterischi di WhatsApp, chiudi ricordando che si può "
    "rispondere STOP per non ricevere più messaggi.\n"
    "- Indica sempre il periodo di validità se fornito.\n"
    "- Hashtag: includi quelli del negozio, poi pochi altri pertinenti, senza il simbolo #."
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


CATEGORY_EMOJI = {
    "frutta e verdura": "🍎", "carne": "🥩", "pesce": "🐟", "salumi e formaggi": "🧀", "latte e latticini": "🥛",
    "uova": "🥚", "pane e forno": "🥖", "pasta e riso": "🍝", "dispensa": "🥫", "surgelati": "❄️",
    "dolci e snack": "🍪", "colazione": "☕", "bevande": "🥤", "vino e alcolici": "🍷", "igiene casa": "🧽",
    "cura persona": "🧴", "infanzia": "🍼", "animali": "🐾", "altro": "🛒",
}
TONES = ("familiare", "elegante", "giovane", "essenziale")


def _short_line(o: Offer, emoji: bool) -> str:
    name = f"{o.brand} {o.name}".strip() if o.brand and o.brand.lower() not in o.name.lower() else o.name
    if o.description:
        name += f" {o.description}"
    line = f"{name}: {format_eur(o.price_cents)}"
    if o.discount_percent:
        line += f" (-{o.discount_percent}%)"
    elif o.old_price_cents:
        line += f" invece di {format_eur(o.old_price_cents)}"
    if o.conditions:
        line += f", {o.conditions}"
    return (CATEGORY_EMOJI.get(o.category, "🛒") + " " if emoji else "• ") + line


def _hook(offers: list[Offer], tone: str) -> str:
    """Frase d'apertura costruita sull'offerta più forte (mai inventata)."""
    best = max(offers, key=lambda o: (o.discount_percent or 0, -o.price_cents))
    name = best.name
    if best.discount_percent and best.discount_percent >= 15:
        return {"elegante": f"Questa settimana: {name} con il {best.discount_percent}% di sconto.",
                "giovane": f"-{best.discount_percent}% su {name}?! Sì, hai letto bene 🔥",
                "essenziale": f"{name} a {format_eur(best.price_cents)} (-{best.discount_percent}%)."}.get(
            tone, f"Fino al -{best.discount_percent}% sulla spesa di questa settimana!")
    cheapest = min(offers, key=lambda o: o.price_cents)
    return {"elegante": "Le nostre proposte della settimana.",
            "giovane": f"Spesa smart: {cheapest.name} a soli {format_eur(cheapest.price_cents)} 😍",
            "essenziale": "Le offerte della settimana."}.get(tone, "Sono arrivate le nuove offerte!")


def template_pack(store: Store, flyer: Flyer, offers: list[Offer]) -> dict[str, dict]:
    """Testi pronti senza IA: curati, con il tono di voce del negozio, prezzi sempre esatti."""
    tone = store.tone if store.tone in TONES else "familiare"
    emoji = tone != "elegante"
    validity = validity_text(flyer)
    when = f" {validity}" if validity else ""
    where = ", ".join(x for x in (store.address, store.city) if x)
    hours = "; ".join(f"{k} {v}" for k, v in (store.opening_hours or {}).items())
    lines = "\n".join(_short_line(o, emoji) for o in offers)
    hook = _hook(offers, tone) if offers else "Le offerte della settimana."
    cta = {"elegante": f"Vi aspettiamo{(' in ' + where) if where else ''}.",
           "giovane": f"Ci vediamo in negozio{(' in ' + where) if where else ''}! 🛒",
           "essenziale": f"{store.name}{(' – ' + where) if where else ''}."}.get(
        tone, f"Ti aspettiamo{(' in ' + where) if where else ''}! 😊")

    tags = list(dict.fromkeys([*(store.hashtags or []), "offerte", "volantino", "spesa", "risparmio",
                               "supermercato"]))
    if store.city:
        tags.append(re.sub(r"\W", "", store.city.lower()))
    tags = list(dict.fromkeys(t for t in tags if t))[:12]

    ig = f"{hook}\n\n{lines}\n\n📅 Offerte valide{when}.\n{cta}" if validity else f"{hook}\n\n{lines}\n\n{cta}"
    if not emoji:
        ig = ig.replace("📅 ", "")
    fb_intro = {"elegante": f"È disponibile il nuovo volantino di {store.name}{when}.",
                "giovane": f"Nuovo volantino {store.name}{when} e sconti che non puoi perdere 👇",
                "essenziale": f"Volantino {store.name}{when}."}.get(
        tone, f"È uscito il nuovo volantino di {store.name}{when}! Ecco alcune delle offerte che ti aspettano:")
    fb = f"{fb_intro}\n\n{lines}\n\n{cta}"
    if hours:
        fb += f"\nOrari: {hours}."
    wa_lines = "\n".join(f"{_short_line(o, emoji).split(': ')[0]}: *{format_eur(o.price_cents)}*"
                          + (f" (-{o.discount_percent}%)" if o.discount_percent else "") for o in offers)
    wa = (f"*{store.name}* – nuove offerte{when} 🛒\n\n{wa_lines}\n\n{cta}"
          + ("\n" + f"Orari: {hours}" if hours else "") + "\n\nRispondi STOP per non ricevere più messaggi.")
    if not emoji:
        wa = wa.replace(" 🛒", "")
    best = max(offers, key=lambda o: (o.discount_percent or 0)) if offers else None
    subject = (f"{best.name} a {format_eur(best.price_cents)} e le altre offerte di {store.name}"
               if best else f"Le nuove offerte di {store.name}")[:80]
    plain = "\n".join(_short_line(o, False) for o in offers)
    body = (f"Ciao,\n\n{hook}\n\nEcco una selezione dal nuovo volantino di {store.name}{when}:\n\n{plain}\n\n"
            f"{cta}" + (f"\nOrari: {hours}." if hours else "") +
            f"\n\nA presto,\nlo staff di {store.name}\n\nOfferte valide fino a esaurimento scorte.")
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
            f"Tono di voce: {store.tone or 'familiare'}\n"
            f"Hashtag del negozio: {', '.join(store.hashtags or []) or '-'}\n"
            f"Orari: {'; '.join(f'{k} {v}' for k, v in (store.opening_hours or {}).items()) or '-'}\n"
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
    """Salva i testi; quelli già presenti per questo volantino vengono sostituiti (niente doppioni)."""
    for old in session.scalars(select(ContentPiece).where(ContentPiece.flyer_id == flyer.id,
                                                          ContentPiece.kind.in_(KINDS))).all():
        session.delete(old)
    session.flush()
    pieces = []
    for kind in KINDS:
        t = pack.texts[kind]
        piece = ContentPiece(store_id=store.id, flyer_id=flyer.id, kind=kind, title=t["title"], body=t["body"],
                             meta={**t.get("meta", {}), "source": pack.source})
        session.add(piece)
        pieces.append(piece)
    session.flush()
    return pieces
