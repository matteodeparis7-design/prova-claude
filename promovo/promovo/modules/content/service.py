"""Agente "Testi": la comunicazione della settimana a partire dalle offerte.

Il lavoro lo fa la redazione interna di Promovo (writer.py), da sola e senza collegamenti esterni:
fatti calcolati dal codice, un'idea per la settimana, testi per canale nel tono del negozio,
rilettura finale. Se è attiva la chiave facoltativa dell'IA, Claude può proporre una versione
alternativa di Instagram e Facebook: viene usata solo se passa gli stessi controlli (prezzi veri,
nessuna frase fatta), altrimenti resta il testo della redazione.

Accanto ai testi prepara il piano della settimana: cosa pubblicare, dove e in che giorno,
e cosa filmare al banco per il Reel.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...llm import AIRefused, AIUnavailable, LLM
from ...models import ContentPiece, Flyer, Offer, Store
from ...money import find_prices, format_eur
from .writer import (BANNED, CATEGORY_EMOJI, TONES, Facts, featured_offers, fmt_date, fmt_day, gather_facts,
                     hero_offer, product_name, review, saving, shoot_ideas, validity_text, week_dates, write_week)

log = logging.getLogger("promovo.content")

__all__ = ["KINDS", "TONES", "AI_TELLS", "CATEGORY_EMOJI", "ContentPack", "generate_content", "save_content",
           "weekly_plan", "template_pack", "featured_offers", "hero_offer", "product_name", "validity_text",
           "fmt_date", "fmt_day", "saving", "ai_tells", "prices_ok"]

KINDS = ("instagram", "facebook", "plan")
AI_TELLS = BANNED


def ai_tells(text: str) -> list[str]:
    """Le frasi fatte rimaste in un testo (vuoto se è pulito)."""
    low = text.lower()
    found = [t for t in AI_TELLS if t in low]
    if "—" in text:
        found.append("trattino lungo")
    if text.count("!") > 2:
        found.append("troppi punti esclamativi")
    return found


def prices_ok(text: str, allowed: set[int]) -> bool:
    return all(p in allowed for p in find_prices(text))


@dataclass
class ContentPack:
    texts: dict[str, dict]           # kind -> {"title", "body", "meta"}
    source: str                      # "agents" | "ai"
    warnings: list[str] = field(default_factory=list)


# ------------------------------------------------------------------ piano della settimana

def weekly_plan(store: Store, flyer: Flyer, offers: list[Offer], today: date | None = None,
                hero: Offer | None = None, weather: dict | None = None, facts: Facts | None = None,
                angle=None) -> str:
    """Cosa pubblicare, dove e quando, con i materiali che Promovo ha appena creato."""
    start, end = week_dates(flyer, today)
    span = (end - start).days
    hero = hero or (hero_offer(offers) if offers else None)
    others = [o for o in featured_offers(flyer) if o is not hero]

    def day(n: int) -> date:
        return start + timedelta(days=min(max(n, 0), span))

    friday = next((start + timedelta(days=i) for i in range(2, span + 1)
                   if (start + timedelta(days=i)).weekday() == 4), None)
    items: list[tuple[date, str, str, str]] = [
        (day(0), "ore 12:30", "Instagram e TikTok · Reel 9:16",
         "Apre la settimana: il Reel con le offerte migliori. Come testo usa «Post Instagram»."),
        (day(0), "ore 19:00", "Facebook · Video 1:1",
         "Stesso giorno, pubblico diverso. Come testo usa «Post Facebook»."),
    ]
    if hero is not None:
        items.append((day(1), "ore 18:00", "Instagram · Post con immagine",
                      f"L'immagine di «{product_name(hero, False)}», il prodotto protagonista."))
    if span >= 2:
        items.append((day(2), "ore 12:00", "Instagram e Facebook · Reel dal banco",
                      "Un video girato in negozio (vedi sotto cosa filmare), montato da Promovo nella sezione «Dal banco»."))
    if friday is not None and others:
        items.append((friday, "ore 17:30", "Instagram e Facebook · Storia",
                      f"Per il fine settimana: l'immagine di «{product_name(others[0], False)}»."))
    if span >= 3:
        items.append((day(span), "ore 9:00", "Instagram · Storia con la copertina",
                      "Ultimo giorno di offerte: la storia con tutte le offerte e la data di fine."))
    # Meteo: nei giorni di caldo, freddo o pioggia, una storia con i prodotti che il tempo fa vendere.
    for a in ((weather or {}).get("advice") or [])[:2]:
        try:
            d = date.fromisoformat(a["date"])
        except (KeyError, ValueError, TypeError):
            continue
        if not (start <= d <= end) or not a.get("offers"):
            continue
        word = {"caldo": f"caldo, {a.get('tmax')} °C", "freddo": f"freddo, {a.get('tmax')} °C di massima",
                "pioggia": "pioggia"}.get(a.get("signal"), a.get("signal", ""))
        names = ", ".join(o["name"] for o in a["offers"][:3])
        items.append((d, "ore 11:00", "Instagram e Facebook · Storia", f"Previsto {word}: metti in storia {names}."))
    items.append((day(0), "per tutta la settimana", "Televisori in negozio · Video schermo 16:9",
                  "In loop alla cassa e all'ingresso: mostra tutte le offerte."))
    items.sort(key=lambda x: (x[0], x[1] == "per tutta la settimana", x[1]))
    lines = []
    for d, at, where, what in items:
        when = f"Da {fmt_day(d)[0].lower()}{fmt_day(d)[1:]}, {at}" if at.startswith("per tutta") else f"{fmt_day(d)}, {at}"
        lines.append(f"{when}\n{where}\n{what}")
    head = f"Piano consigliato per il volantino {validity_text(flyer)}".strip() + "."
    out = head + "\n\n" + "\n\n".join(lines)
    facts = facts or (gather_facts(store, flyer, offers, weather, today) if offers else None)
    ideas = shoot_ideas(facts, angle) if facts is not None else []
    if ideas:
        out += "\n\nCOSA FILMARE AL BANCO (per il Reel)\n" + "\n".join(f"- {i}" for i in ideas)
    return out + "\n\nGli orari sono un punto di partenza: tienili se funzionano, spostali se il tuo pubblico è attivo in altri momenti."


# ------------------------------------------------------------------ la redazione interna

def template_pack(store: Store, flyer: Flyer, offers: list[Offer], weather: dict | None = None,
                  today: date | None = None) -> dict[str, dict]:
    """I testi della redazione interna (senza IA esterna), con il piano della settimana."""
    w = write_week(store, flyer, offers, weather=weather, today=today)
    texts = dict(w.texts)
    hero = (w.angle.featured[0] if w.angle and w.angle.featured else None)
    texts["plan"] = {"title": "Piano della settimana",
                     "body": weekly_plan(store, flyer, offers, today=today, hero=hero, weather=weather,
                                         facts=w.facts, angle=w.angle), "meta": {}}
    for t in texts.values():
        t.setdefault("meta", {})
    if w.issues:
        log.warning("testi della redazione con difetti: %s", w.issues)
    return texts


# ------------------------------------------------------------------ con l'IA (facoltativa)

class AIContent(BaseModel):
    strategia: str = Field(default="", description="L'idea della settimana in 2-3 frasi. Si scrive prima dei testi.")
    instagram_caption: str = Field(description="Didascalia Instagram senza hashtag")
    hashtags: list[str] = Field(description="6-10 hashtag senza il simbolo #")
    facebook_post: str = Field(description="Post Facebook")


_SYSTEM = f"""\
Sei il copywriter di un supermercato di quartiere italiano. Scrivi come scriverebbe il titolare:
frasi vere, concrete, misurate. Chi legge non deve mai pensare "questo l'ha scritto un'IA".

Ricevi i fatti della settimana, già calcolati, e una bozza della redazione. Migliorala solo se
puoi fare davvero meglio: un'apertura più forte, un ritmo più naturale. Altrimenti tienila.

PRINCIPI
- Numeri, non aggettivi. Il risparmio in euro conta più della percentuale.
- La prima riga di Instagram (max 90 caratteri) nomina il prodotto o l'idea e il suo numero.
- Una frase, un'informazione. Al massimo un punto esclamativo. Niente domande retoriche in apertura.
- Emoji: al massimo 2 per testo, solo con tono familiare o giovane.
- Chiudi con un'informazione utile (fino a quando, dove, orari).
- Parole vietate: {", ".join(BANNED[:30])}.

REGOLE TASSATIVE
- Usa SOLO prodotti, prezzi e totali forniti, scritti esattamente così (es. "€ 1,99").
  Non fare calcoli tuoi. Non inventare prodotti, sconti, date, servizi o qualità del prodotto.
- Tono: familiare (tu, caldo), elegante (voi, sobrio, nessuna emoji), giovane (tu, ritmo veloce),
  essenziale (informativo, nessuna emoji).
"""


def _ai_brief(f: Facts, draft: dict[str, dict]) -> str:
    rows = []
    for o in f.offers:
        bits = [f"prezzo {format_eur(o.price_cents)}"]
        if o.old_price_cents:
            bits += [f"prima {format_eur(o.old_price_cents)}", f"risparmio {format_eur(saving(o))}"]
        if o.conditions:
            bits.append(o.conditions)
        rows.append(f"- [{o.category}] {product_name(o)}: " + "; ".join(bits))
    combos = "\n".join(f"- {c.recipe.title}: {c.names} = {format_eur(c.total_cents)} in tutto" for c in f.combos[:2])
    return (f"NEGOZIO: {f.store.name} · {f.where or '-'} · orari {f.hours or '-'} · tono {f.tone}\n"
            f"VALIDITÀ: {f.validity or 'non indicata'}\n\nOFFERTE\n" + "\n".join(rows) +
            (f"\n\nCENE COMPLETE CON LE OFFERTE (totali già calcolati)\n{combos}" if combos else "") +
            f"\n\nBOZZA DELLA REDAZIONE\n[Instagram]\n{draft['instagram']['body']}\n\n[Facebook]\n{draft['facebook']['body']}")


def generate_content(store: Store, flyer: Flyer, llm: LLM | None, weather: dict | None = None,
                     today: date | None = None) -> ContentPack:
    offers = featured_offers(flyer)
    texts = template_pack(store, flyer, offers, weather=weather, today=today)
    if not offers:
        return ContentPack(texts=texts, source="agents", warnings=["Nessuna offerta nel volantino."])
    if llm is None:
        return ContentPack(texts=texts, source="agents")
    f = gather_facts(store, flyer, offers, weather, today)
    from .writer import computed_prices
    allowed = computed_prices(f)
    try:
        ai = llm.parse(system=_SYSTEM, content=[{"type": "text", "text": _ai_brief(f, texts)}], schema=AIContent,
                       effort="high", max_tokens=8000)
    except (AIUnavailable, AIRefused) as exc:
        return ContentPack(texts=texts, source="agents", warnings=[f"IA facoltativa non disponibile: {exc}"])
    warnings, used = [], False
    for kind, body in (("instagram", ai.instagram_caption), ("facebook", ai.facebook_post)):
        body = (body or "").strip()
        problems = review(body, allowed, f.tone) if body else ["testo vuoto"]
        if problems:
            warnings.append(f"Proposta dell'IA per {kind} scartata ({problems[0]}): resta il testo degli agenti.")
            continue
        texts[kind] = {**texts[kind], "body": body}
        used = True
    tags = [h.lstrip("#").strip() for h in ai.hashtags if h.strip()][:10]
    if used and tags:
        texts["instagram"]["meta"] = {**texts["instagram"].get("meta", {}), "hashtags": tags}
    if used and ai.strategia:
        texts["instagram"]["meta"] = {**texts["instagram"].get("meta", {}), "strategy": ai.strategia.strip()}
    return ContentPack(texts=texts, source="ai" if used else "agents", warnings=warnings)


def save_content(session: Session, store: Store, flyer: Flyer, pack: ContentPack) -> list[ContentPiece]:
    """Salva i testi; quelli già presenti per questo volantino vengono sostituiti (niente doppioni)."""
    old_kinds = (*KINDS, "whatsapp", "newsletter", "whatsapp_personal")
    for old in session.scalars(select(ContentPiece).where(ContentPiece.flyer_id == flyer.id,
                                                          ContentPiece.kind.in_(old_kinds))).all():
        session.delete(old)
    session.flush()
    pieces = []
    for kind in KINDS:
        t = pack.texts.get(kind)
        if not t:
            continue
        piece = ContentPiece(store_id=store.id, flyer_id=flyer.id, kind=kind, title=t["title"], body=t["body"],
                             meta={**t.get("meta", {}), "source": pack.source if kind != "plan" else "plan"})
        session.add(piece)
        pieces.append(piece)
    session.flush()
    return pieces
