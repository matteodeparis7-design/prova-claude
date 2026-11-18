"""Agente "Copywriter": la comunicazione della settimana a partire dalle offerte.

Lavora come una piccola redazione:
1. i numeri li calcola il codice (risparmio in euro, prezzi sotto l'euro, giorni di validità,
   fine settimana, periodo dell'anno): l'IA non deve fare conti né inventare;
2. il copywriter (Claude) sceglie un'idea forte e scrive i testi per ogni canale;
3. il caporedattore (Claude, seconda passata) rilegge, toglie tutto ciò che "suona da IA"
   e controlla di nuovo prezzi e regole;
4. il codice verifica che ogni prezzo citato esista davvero e che non restino frasi fatte.
Senza IA i testi vengono da modelli scritti a mano, con la stessa logica dei numeri.

Accanto ai testi prepara il piano della settimana: cosa pubblicare, dove e in che giorno.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date, timedelta

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

KINDS = ("instagram", "facebook", "whatsapp", "newsletter", "plan")
TONES = ("familiare", "elegante", "giovane", "essenziale")
STOP_LINE = "Rispondi STOP per non ricevere più messaggi."


def fmt_date(d: date | None) -> str:
    return f"{d.day} {_MESI[d.month - 1]}" if d else ""


def fmt_day(d: date) -> str:
    return f"{_GIORNI[d.weekday()].capitalize()} {fmt_date(d)}"


def validity_text(flyer: Flyer) -> str:
    vf, vt = flyer.valid_from, flyer.valid_to
    if vf and vt:
        if (vf.month, vf.year) == (vt.month, vt.year):
            return f"dal {vf.day} al {fmt_date(vt)}"           # dal 13 al 22 novembre
        return f"dal {fmt_date(vf)} al {fmt_date(vt)}"
    if flyer.valid_to:
        return f"fino al {fmt_date(flyer.valid_to)}"
    return ""


def product_name(o: Offer, size: bool = True) -> str:
    name = f"{o.brand} {o.name}".strip() if o.brand and o.brand.lower() not in o.name.lower() else o.name
    if size and o.description:
        name += f" {o.description}"
    return name


def offer_line(o: Offer) -> str:
    line = f"{product_name(o, False)}{f' ({o.description})' if o.description else ''} a {format_eur(o.price_cents)}"
    if o.old_price_cents:
        line += f" invece di {format_eur(o.old_price_cents)}"
    if o.discount_percent:
        line += f" (-{o.discount_percent}%)"
    if o.conditions:
        line += f", {o.conditions}"
    return line


def saving(o: Offer) -> int:
    """Risparmio in centesimi su un pezzo (0 se il prezzo vecchio non è stampato)."""
    return max(0, (o.old_price_cents or 0) - o.price_cents)


def featured_offers(flyer: Flyer, limit: int = 6) -> list[Offer]:
    feat = [o for o in flyer.offers if o.is_featured]
    rest = sorted((o for o in flyer.offers if not o.is_featured),
                  key=lambda o: (-(o.discount_percent or 0), o.price_cents))
    return (feat + rest)[:limit]


def hero_offer(offers: list[Offer]) -> Offer:
    """L'offerta su cui costruire la comunicazione: quella messa in evidenza, o lo sconto più forte."""
    feat = [o for o in offers if o.is_featured]
    pool = feat or offers
    return max(pool, key=lambda o: (o.discount_percent or 0, saving(o), -o.price_cents))


# ------------------------------------------------------------------ i fatti, calcolati dal codice

def occasions(flyer: Flyer, today: date | None = None) -> list[str]:
    """Il contesto reale della settimana: niente ricorrenze inventate."""
    start = flyer.valid_from or today or date.today()
    end = flyer.valid_to or start + timedelta(days=6)
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)][:21]
    out = []
    if any(d.weekday() >= 5 for d in days):
        out.append("il volantino copre un fine settimana")
    season = {12: "inverno, feste di Natale", 1: "inverno, ripresa dopo le feste", 2: "inverno, Carnevale",
              3: "primavera", 4: "primavera, Pasqua", 5: "primavera", 6: "inizio estate", 7: "estate piena",
              8: "estate, Ferragosto", 9: "rientro dalle vacanze, scuola", 10: "autunno",
              11: "autunno, primo freddo"}[start.month]
    out.append(f"periodo: {season}")
    for d in days:
        if (d.month, d.day) == (12, 25) or (d.month == 12 and d.day >= 18):
            out.append("si avvicina il Natale: spesa per le feste")
            break
    if any(d.day >= 27 for d in days):
        out.append("fine mese: chi fa la spesa guarda di più il conto")
    if (end - start).days <= 4:
        out.append(f"offerta breve: solo {(end - start).days + 1} giorni")
    return out


def offer_facts(offers: list[Offer]) -> str:
    rows = []
    for o in offers:
        bits = [f"prezzo {format_eur(o.price_cents)}"]
        if o.old_price_cents:
            bits.append(f"prima {format_eur(o.old_price_cents)}")
            bits.append(f"risparmio {format_eur(saving(o))} a pezzo")
        if o.discount_percent:
            bits.append(f"sconto {o.discount_percent}%")
        if o.price_cents < 100:
            bits.append("costa meno di un euro")
        if o.unit_price_text:
            bits.append(f"prezzo al kg/l: {o.unit_price_text}")
        if o.conditions:
            bits.append(f"condizioni: {o.conditions}")
        if o.is_featured:
            bits.append("MESSA IN EVIDENZA DAL NEGOZIO")
        rows.append(f"- [{o.category}] {product_name(o)}: " + "; ".join(bits))
    return "\n".join(rows)


# ------------------------------------------------------------------ regole di stile

# Frasi e parole che fanno sembrare un testo scritto da un'IA o da un volantino anonimo.
AI_TELLS = [
    "imperdibil", "non perdere", "non lasciart", "scopri", "che aspetti", "affrettati", "corri",
    "occasione unica", "delizi", "gusto unico", "sapori autentici", "viaggio", "esperienza",
    "qualità superiore", "il meglio per te", "merita il meglio", "risparmio garantito", "irresistibil",
    "coccol", "a portata di mano", "a prezzi imbattibili", "prezzi pazzi", "super offert", "mega",
    "tutto questo e molto altro", "e tanto altro", "sei pronto", "siete pronti", "lasciati",
    "concediti", "regalati", "immergiti", "esplora", "ti aspettano tante", "fantastic", "incredibil",
    "straordinari", "eccezional", "pazzesc", "top!", "wow",
]

_SYSTEM = """\
Sei il copywriter di un supermercato di quartiere italiano. Scrivi come scriverebbe il titolare,
o la persona simpatica al banco che conosce i clienti per nome: frasi vere, concrete, misurate.
Il tuo lavoro deve essere indistinguibile da quello di un bravo professionista umano:
chi legge non deve mai pensare "questo l'ha scritto un'intelligenza artificiale".

COME LAVORI
1. Prima di scrivere scegli UNA idea per la settimana, nel campo "strategia": il prodotto protagonista
   (di solito quello messo in evidenza dal negozio o con il risparmio più forte) e il motivo concreto
   per cui interessa a chi fa la spesa: un risparmio in euro, un prezzo sotto l'euro, un momento d'uso
   reale (la cena del venerdì, la colazione, la scorta per la settimana), il periodo dell'anno.
2. Ogni canale ha un lavoro diverso: non ripetere lo stesso testo quattro volte.

PRINCIPI DI SCRITTURA
- Numeri, non aggettivi. "€ 0,50 in meno sul pacco da 500 g" convince; "prezzo incredibile" no.
- Il risparmio in euro conta più della percentuale; usa la percentuale solo se è grande.
- Una frase, un'informazione. Frasi brevi. Niente frasi fatte, niente slogan.
- Nomina il prodotto con il formato (500 g, 1 l): è quello che il cliente cerca sullo scaffale.
- Al massimo un punto esclamativo per testo. Nessuna domanda retorica in apertura.
- Emoji: al massimo 2 per testo, mai una per riga, mai in fila. Con il tono elegante o essenziale: nessuna.
- Il trattino lungo (—) non si usa. Niente elenchi di tre aggettivi.
- Chiudi con un'informazione utile (dove, fino a quando, orari), non con un invito generico.

PAROLE E FRASI VIETATE (suonano finte o da IA): imperdibile, non perdere, scopri, che aspetti,
affrettati, corri, occasione unica, delizia, gusto unico, sapori autentici, viaggio, esperienza,
qualità superiore, il meglio per te, risparmio garantito, irresistibile, coccolati, concediti,
regalati, lasciati tentare, a portata di mano, prezzi imbattibili, fantastico, incredibile,
straordinario, eccezionale, e molto altro, sei pronto.

REGOLE TASSATIVE
- Usa SOLO i prodotti, i prezzi e i risparmi forniti, scritti esattamente come sono dati (es. "€ 1,99").
  Non fare somme o calcoli tuoi. Non inventare prodotti, sconti, date, servizi, consegne, promesse.
- Se il periodo di validità è dato, citalo sempre.

TONO DI VOCE DEL NEGOZIO
- familiare: dà del tu, caldo e alla mano, come un vicino di casa. Max 2 emoji.
- elegante: dà del voi, sobrio e curato, lessico preciso, nessuna emoji.
- giovane: dà del tu, ritmo veloce, frasi molto corte, un pizzico d'ironia, max 2 emoji.
- essenziale: informativo, quasi telegrafico, nessuna emoji.

I CANALI
- instagram_caption: la prima riga (max 90 caratteri) è tutto: deve far fermare il pollice con il
  prodotto protagonista e il suo numero. Poi 3-5 righe con altre 2-4 offerte scritte come frasi o
  righe pulite, poi validità e indirizzo. Gli hashtag NON vanno nel testo.
- hashtags: 6-10, senza #. Prima quelli del negozio, poi la città, poi pochi pertinenti in italiano.
- facebook_post: il pubblico è più adulto e legge di più. Tono da conversazione, può elencare tutte
  le offerte fornite (una per riga, prodotto + formato + prezzo), chiude con indirizzo e orari.
- whatsapp_message: è un messaggio personale del negozio al cliente, non una pubblicità.
  Max 600 caratteri. Saluto breve con il nome del negozio, 3-4 offerte con il prezzo in *grassetto*
  (asterischi di WhatsApp), validità, una riga con indirizzo o orari, e in fondo esattamente:
  "Rispondi STOP per non ricevere più messaggi."
- newsletter_subject: max 45 caratteri, concreto: prodotto e prezzo. Niente maiuscole urlate.
- newsletter_body: 3-4 paragrafi brevi; apre sull'idea della settimana, poi le offerte in righe pulite,
  poi validità, indirizzo e orari. Firma: "lo staff di <negozio>".

ESEMPI (tono familiare)
Male: "🔥 Offerte imperdibili! Scopri il nostro volantino ricco di sorprese, non lasciartele scappare! 🛒🎉"
Bene: "Spaghetti 500 g a € 0,79 invece di € 1,29: fino a domenica li trovi così."
Male: "Un viaggio nel gusto con il nostro salmone dalla qualità superiore!"
Bene: "Salmone affumicato 100 g a € 3,49. Per la cena del venerdì, con un filo d'olio e due fette di pane."
"""

_EDITOR = """\
Sei il caporedattore di un'agenzia che cura la comunicazione di supermercati italiani.
Ricevi le bozze del copywriter e le regole del cliente. Il tuo compito è renderle indistinguibili
da testi scritti da un professionista umano, senza perdere alcuna informazione vera.

PROCEDURA
1. Nel campo "difetti" elenca con precisione ogni problema trovato, per esempio:
   - frasi fatte o parole vietate (imperdibile, scopri, non perdere, delizia, viaggio, esperienza,
     incredibile, fantastico, irresistibile, concediti, e molto altro...);
   - aggettivi al posto dei numeri; aperture vaghe; domande retoriche; troppi punti esclamativi;
   - troppe emoji, emoji a ogni riga, trattini lunghi (—), elenchi di tre aggettivi;
   - testi uguali tra canali; prima riga Instagram che non nomina prodotto e prezzo;
   - prezzi, risparmi o date diversi da quelli forniti, calcoli fatti dal copywriter, promesse inventate;
   - tono diverso da quello richiesto (tu/voi, emoji ammesse o no);
   - WhatsApp più lungo di 600 caratteri o senza la riga finale sullo STOP.
2. Riscrivi TUTTI i campi correggendo ogni difetto. Se una bozza è già buona, ritoccala il minimo.
   Mantieni gli stessi prezzi scritti nello stesso formato (es. "€ 0,79"). Non aggiungere nulla
   che non sia nei dati forniti.
"""


class AIContent(BaseModel):
    strategia: str = Field(default="", description="L'idea della settimana: prodotto protagonista e perché, "
                                                    "in 2-3 frasi. Si scrive prima dei testi.")
    instagram_caption: str = Field(description="Didascalia Instagram senza hashtag")
    hashtags: list[str] = Field(description="6-10 hashtag senza il simbolo #")
    facebook_post: str = Field(description="Post Facebook")
    whatsapp_message: str = Field(description="Messaggio WhatsApp, max 600 caratteri, con la riga dello STOP")
    newsletter_subject: str = Field(description="Oggetto email, max 45 caratteri")
    newsletter_body: str = Field(description="Testo email in paragrafi brevi")


class AIEdited(BaseModel):
    difetti: list[str] = Field(default_factory=list, description="Ogni problema trovato nelle bozze")
    instagram_caption: str
    hashtags: list[str]
    facebook_post: str
    whatsapp_message: str
    newsletter_subject: str
    newsletter_body: str


@dataclass
class ContentPack:
    texts: dict[str, dict]           # kind -> {"title", "body", "meta"}
    source: str                      # "ai" | "template"
    warnings: list[str] = field(default_factory=list)


def _allowed_prices(offers: list[Offer], store: Store | None = None) -> set[int]:
    allowed: set[int] = set()
    for o in offers:
        allowed.add(o.price_cents)
        if o.old_price_cents:
            allowed.update((o.old_price_cents, saving(o)))
    if store is not None:   # orari come "8.30-13.00" non sono prezzi
        allowed.update(find_prices(" ".join(f"{k} {v}" for k, v in (store.opening_hours or {}).items())))
    return allowed


def prices_ok(text: str, allowed: set[int]) -> bool:
    return all(p in allowed for p in find_prices(text))


def ai_tells(text: str) -> list[str]:
    """Le frasi fatte rimaste in un testo (vuoto se è pulito)."""
    low = text.lower()
    found = [t for t in AI_TELLS if t in low]
    if "—" in text:
        found.append("trattino lungo")
    if text.count("!") > 2:
        found.append("troppi punti esclamativi")
    return found


CATEGORY_EMOJI = {
    "frutta e verdura": "🍎", "carne": "🥩", "pesce": "🐟", "salumi e formaggi": "🧀", "latte e latticini": "🥛",
    "uova": "🥚", "pane e forno": "🥖", "pasta e riso": "🍝", "dispensa": "🥫", "surgelati": "❄️",
    "dolci e snack": "🍪", "colazione": "☕", "bevande": "🥤", "vino e alcolici": "🍷", "igiene casa": "🧽",
    "cura persona": "🧴", "infanzia": "🍼", "animali": "🐾", "altro": "🛒",
}

# Un momento d'uso reale per categoria: dà concretezza senza inventare nulla sul prodotto.
MOMENT = {
    "pasta e riso": "per il pranzo di tutta la settimana", "dispensa": "da tenere in dispensa",
    "colazione": "per la colazione", "dolci e snack": "per la merenda", "pesce": "per la cena del venerdì",
    "carne": "per il pranzo della domenica", "salumi e formaggi": "per un tagliere senza pensieri",
    "latte e latticini": "per tutta la famiglia", "frutta e verdura": "di stagione",
    "igiene casa": "per fare scorta", "cura persona": "per fare scorta", "bevande": "per la tavola",
    "vino e alcolici": "per la cena con gli amici", "surgelati": "per le sere di fretta",
    "pane e forno": "per la tavola", "infanzia": "per i più piccoli", "animali": "per i tuoi animali",
}


# ------------------------------------------------------------------ testi senza IA, scritti a mano

def _price_phrase(o: Offer) -> str:
    p = format_eur(o.price_cents)
    return f"{p} invece di {format_eur(o.old_price_cents)}" if o.old_price_cents else p


def _hook(hero: Offer, tone: str, variant: int) -> str:
    """Prima riga: prodotto protagonista e il suo numero. Mai aggettivi vuoti."""
    name, price = product_name(hero), _price_phrase(hero)
    sv = saving(hero)
    if tone == "essenziale":
        return f"{name}: {price}."
    if tone == "elegante":
        lower = name if hero.brand else name[:1].lower() + name[1:]
        return f"Questa settimana vi proponiamo {lower} a {price}."
    options = [f"{name} a {price}."]
    if sv >= 30:
        options.append(f"{name}: {format_eur(sv)} in meno a confezione, a {format_eur(hero.price_cents)}.")
    if hero.price_cents < 100:
        options.append(f"Meno di un euro: {name} a {format_eur(hero.price_cents)}.")
    if hero.discount_percent and hero.discount_percent >= 40:
        options.append(f"{name} quasi a metà prezzo: {price}.")
    line = options[variant % len(options)]
    if tone == "giovane" and len(options) > 1:
        line = options[-1]
    return line


def _offer_row(o: Offer, bold: bool = False) -> str:
    p = format_eur(o.price_cents)
    p = f"*{p}*" if bold else p
    row = f"{product_name(o)} {p}"
    if o.old_price_cents:
        row += f" (prima {format_eur(o.old_price_cents)})"
    if o.conditions:
        row += f", {o.conditions}"
    return row


def template_pack(store: Store, flyer: Flyer, offers: list[Offer]) -> dict[str, dict]:
    """Testi pronti senza IA: un'idea per settimana, numeri veri, tono del negozio, nessuna frase fatta."""
    tone = store.tone if store.tone in TONES else "familiare"
    voi = tone == "elegante"
    emoji_ok = tone in ("familiare", "giovane")
    validity = validity_text(flyer)
    where = ", ".join(x for x in (store.address, store.city) if x)
    hours = "; ".join(f"{k} {v}" for k, v in (store.opening_hours or {}).items())
    tags = list(dict.fromkeys([*(store.hashtags or []),
                               re.sub(r"\W", "", (store.city or "").lower()),
                               "offertesettimana", "spesa", "volantino", "risparmio"]))
    tags = [t for t in tags if t][:10]
    if not offers:
        empty = f"Le offerte di {store.name}" + (f", {validity}" if validity else "") + "."
        return {k: {"title": t, "body": empty + (f"\n\n{STOP_LINE}" if k == "whatsapp" else ""),
                    "meta": {"hashtags": tags} if k == "instagram" else {}}
                for k, t in (("instagram", "Post Instagram"), ("facebook", "Post Facebook"),
                             ("whatsapp", "Messaggio WhatsApp"), ("newsletter", f"Le offerte di {store.name}"))} | {
            "plan": {"title": "Piano della settimana", "body": weekly_plan(store, flyer, offers), "meta": {}}}

    hero = hero_offer(offers)
    others = [o for o in offers if o is not hero]
    variant = (flyer.id or 0) + len(offers)
    hook = _hook(hero, tone, variant)
    moment = MOMENT.get(hero.category)
    until = f"Offerte valide {validity}" if validity else ""

    # ---- Instagram: protagonista, poche righe pulite, dove e fino a quando
    second = ""
    if moment and tone in ("familiare", "giovane"):
        second = f"{'Perfetto' if hero.category not in ('igiene casa', 'cura persona') else 'Il momento giusto'} " \
                 f"{moment}."
    intro_others = {"elegante": "Tra le altre proposte:", "essenziale": "Inoltre:",
                    "giovane": "E poi:"}.get(tone, "Nel volantino trovi anche:")
    ig_lines = [hook]
    if second:
        ig_lines.append(second)
    if others:
        ig_lines += ["", intro_others, *(_offer_row(o) for o in others[:4])]
    close = " · ".join(x for x in (until, where) if x)
    if close:
        ig_lines += ["", close]
    ig = "\n".join(ig_lines)
    if emoji_ok:
        ig = ig.replace(hook, f"{hook} {CATEGORY_EMOJI.get(hero.category, '🛒')}", 1)

    # ---- Facebook: più discorsivo, tutte le offerte
    fb_open = {
        "elegante": f"È disponibile il nuovo volantino di {store.name}" + (f", valido {validity}" if validity else "") + ".",
        "essenziale": f"Volantino {store.name}" + (f", {validity}" if validity else "") + ".",
        "giovane": f"Volantino nuovo da {store.name}" + (f", {validity}" if validity else "") + ".",
    }.get(tone, f"Da oggi trovi il nuovo volantino di {store.name}" + (f", valido {validity}" if validity else "") + ".")
    fb_mid = {"elegante": "Le altre offerte che abbiamo selezionato per voi:",
              "essenziale": "Altre offerte:"}.get(tone, "Le altre che ti segnaliamo:")
    fb = "\n".join([fb_open, "", hook, *([""] + [fb_mid] + [_offer_row(o) for o in others] if others else [])])
    tail = []
    if where:
        tail.append(("Vi aspettiamo in " if voi else "Ti aspettiamo in ") + where + "."
                    if tone != "essenziale" else where + ".")
    if hours:
        tail.append(f"Orari: {hours}.")
    if tail:
        fb += "\n\n" + "\n".join(tail)

    # ---- WhatsApp: un messaggio del negozio a un cliente, non una pubblicità
    greet = {"elegante": f"Buongiorno da *{store.name}*.",
             "essenziale": f"*{store.name}*",
             "giovane": f"Ciao da *{store.name}* 👋"}.get(tone, f"Ciao, ti scriviamo da *{store.name}* 👋")
    wa_intro = ("Le offerte di questa settimana" + (f", {validity}" if validity else "") + ":")
    wa_rows = "\n".join("• " + _offer_row(o, bold=True) for o in [hero, *others][:4])
    wa_where = (f"{'Vi' if voi else 'Ti'} aspettiamo in {where}." if where else "") if tone != "essenziale" else where
    wa = "\n".join(x for x in [greet, "", wa_intro, wa_rows, "", wa_where,
                                f"Orari: {hours}" if hours else "", "", STOP_LINE] if x is not None)
    wa = re.sub(r"\n{3,}", "\n\n", wa)

    # ---- Newsletter
    subject = f"{product_name(hero, False)} a {format_eur(hero.price_cents)}"
    if len(subject) > 45:
        subject = f"{hero.name[:30]} a {format_eur(hero.price_cents)}"
    salute = "Buongiorno," if voi else "Ciao,"
    body = "\n".join([
        salute, "",
        hook + (f" {second}" if second else ""), "",
        ("Le altre offerte che vi segnaliamo:" if voi else "Le altre offerte che ti segnaliamo:"),
        *(_offer_row(o) for o in others), "",
        " ".join(x for x in (until + "." if until else "", f"{'Vi' if voi else 'Ti'} aspettiamo in {where}." if where else "",
                             f"Orari: {hours}." if hours else "") if x),
        "", "A presto,", f"lo staff di {store.name}", "",
        "Offerte valide fino a esaurimento scorte.",
    ])
    return {
        "instagram": {"title": "Post Instagram", "body": ig, "meta": {"hashtags": tags}},
        "facebook": {"title": "Post Facebook", "body": fb, "meta": {}},
        "whatsapp": {"title": "Messaggio WhatsApp", "body": wa, "meta": {}},
        "newsletter": {"title": subject, "body": body, "meta": {}},
        "plan": {"title": "Piano della settimana", "body": weekly_plan(store, flyer, offers), "meta": {}},
    }


# ------------------------------------------------------------------ piano della settimana

def weekly_plan(store: Store, flyer: Flyer, offers: list[Offer], today: date | None = None) -> str:
    """Cosa pubblicare, dove e quando, con i materiali che Promovo ha appena creato."""
    start = flyer.valid_from or today or date.today()
    end = flyer.valid_to or start + timedelta(days=6)
    if end < start:
        end = start + timedelta(days=6)
    span = (end - start).days
    hero = hero_offer(offers) if offers else None
    others = [o for o in featured_offers(flyer) if o is not hero]

    def day(n: int) -> date:
        return start + timedelta(days=min(max(n, 0), span))

    weekend = next((start + timedelta(days=i) for i in range(span + 1)
                    if (start + timedelta(days=i)).weekday() == 4), None)   # il venerdì
    items: list[tuple[date, str, str, str]] = [
        (day(0), "ore 12:30", "Instagram e TikTok · Reel 9:16",
         "Apre la settimana: il Reel con le offerte migliori. Usa il testo «Post Instagram»."),
        (day(0), "ore 19:00", "Facebook · Post video 1:1",
         "Stesso giorno, pubblico diverso. Usa il testo «Post Facebook»."),
        (day(1), "ore 10:00", "WhatsApp · Messaggio ai clienti",
         "Il secondo giorno, a metà mattina: è l'orario in cui si legge e si decide la spesa."),
    ]
    if hero is not None:
        items.append((day(2), "ore 18:00", "Instagram · Post con immagine",
                      f"L'immagine di «{product_name(hero, False)}», il prodotto protagonista."))
    if weekend is not None and others:
        items.append((weekend, "ore 17:30", "Instagram e Facebook · Storia",
                      f"Per il fine settimana: l'immagine di «{product_name(others[0], False)}»."))
    if span >= 3:
        items.append((day(span), "ore 9:00", "Instagram · Storia con la copertina",
                      "Ultimo giorno di offerte: la storia con tutte le offerte e la data di fine."))
    items.append((day(0), "per tutta la settimana", "Televisori in negozio · Video schermo 16:9",
                  "In loop alla cassa e all'ingresso: mostra tutte le offerte."))
    items.sort(key=lambda x: (x[0], x[1] == "per tutta la settimana", x[1]))
    lines = []
    for d, at, where, what in items:
        when = f"Da {fmt_day(d)[0].lower()}{fmt_day(d)[1:]}, {at}" if at.startswith("per tutta") else f"{fmt_day(d)}, {at}"
        lines.append(f"{when}\n{where}\n{what}")
    head = f"Piano consigliato per il volantino {validity_text(flyer)}".strip() + "."
    return head + "\n\n" + "\n\n".join(lines) + \
        "\n\nGli orari sono indicativi: dopo qualche settimana, nella sezione Risultati vedi cosa funziona meglio."


# ------------------------------------------------------------------ con l'IA

def _store_info(store: Store, flyer: Flyer, offers: list[Offer]) -> str:
    hero = hero_offer(offers)
    return (
        f"NEGOZIO\nNome: {store.name}\nInsegna: {store.banner or '-'}\n"
        f"Indirizzo: {', '.join(x for x in (store.address, store.city) if x) or '-'}\n"
        f"Orari: {'; '.join(f'{k} {v}' for k, v in (store.opening_hours or {}).items()) or '-'}\n"
        f"Servizi: {', '.join(store.services or []) or '-'}\n"
        f"Tono di voce: {store.tone or 'familiare'}\n"
        f"Hashtag del negozio: {', '.join(store.hashtags or []) or '-'}\n\n"
        f"SETTIMANA\nValidità: {validity_text(flyer) or 'non indicata'}\n"
        f"Contesto: {'; '.join(occasions(flyer))}\n"
        f"Prodotto protagonista suggerito: {product_name(hero)}\n\n"
        f"OFFERTE (con i numeri già calcolati, da usare così come sono)\n{offer_facts(offers)}"
    )


def generate_content(store: Store, flyer: Flyer, llm: LLM | None) -> ContentPack:
    offers = featured_offers(flyer)
    template = template_pack(store, flyer, offers)
    if not offers:
        return ContentPack(texts=template, source="template", warnings=["Nessuna offerta nel volantino."])
    if llm is None:
        return ContentPack(texts=template, source="template")
    info = _store_info(store, flyer, offers)
    try:
        draft = llm.parse(system=_SYSTEM, content=[{"type": "text", "text": info}], schema=AIContent,
                          effort="high", max_tokens=12000)
    except (AIUnavailable, AIRefused) as exc:
        return ContentPack(texts=template, source="template", warnings=[f"IA non disponibile: {exc}"])

    final: AIContent | AIEdited = draft
    try:   # seconda passata: il caporedattore toglie ciò che suona finto
        drafts = draft.model_dump_json(indent=1, exclude={"strategia"})
        final = llm.parse(system=_EDITOR + "\n\nREGOLE DEL CLIENTE\n" + _SYSTEM,
                          content=[{"type": "text", "text": f"{info}\n\nBOZZE DEL COPYWRITER\n{drafts}"}],
                          schema=AIEdited, effort="high", max_tokens=12000)
    except (AIUnavailable, AIRefused) as exc:
        log.info("revisione non disponibile, uso la bozza: %s", exc)

    allowed = _allowed_prices(offers, store)
    meta = {"strategy": draft.strategia} if draft.strategia else {}
    candidates = {
        "instagram": {"title": "Post Instagram", "body": final.instagram_caption.strip(),
                      "meta": {**meta, "hashtags": [h.lstrip("#").strip() for h in final.hashtags if h.strip()][:10]}},
        "facebook": {"title": "Post Facebook", "body": final.facebook_post.strip(), "meta": {}},
        "whatsapp": {"title": "Messaggio WhatsApp", "body": final.whatsapp_message.strip(), "meta": {}},
        "newsletter": {"title": final.newsletter_subject.strip()[:80] or template["newsletter"]["title"],
                       "body": final.newsletter_body.strip(), "meta": {}},
    }
    texts: dict[str, dict] = {}
    warnings = []
    for kind, piece in candidates.items():
        if not piece["body"] or not prices_ok(piece["title"] + "\n" + piece["body"], allowed):
            warnings.append(f"Testo {kind} dell'IA scartato (prezzo non presente nel volantino): "
                            "usato il modello standard.")
            texts[kind] = template[kind]
            continue
        tells = ai_tells(piece["title"] + "\n" + piece["body"])
        if tells:
            warnings.append(f"Testo {kind}: da rileggere, contiene «{', '.join(tells[:3])}».")
        texts[kind] = piece
    if "STOP" not in texts["whatsapp"]["body"]:
        texts["whatsapp"]["body"] += f"\n\n{STOP_LINE}"
    texts["plan"] = template["plan"]
    return ContentPack(texts=texts, source="ai", warnings=warnings)


def save_content(session: Session, store: Store, flyer: Flyer, pack: ContentPack) -> list[ContentPiece]:
    """Salva i testi; quelli già presenti per questo volantino vengono sostituiti (niente doppioni)."""
    for old in session.scalars(select(ContentPiece).where(ContentPiece.flyer_id == flyer.id,
                                                          ContentPiece.kind.in_(KINDS))).all():
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
