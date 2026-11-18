"""La redazione di Promovo: scrive i testi della settimana da sola, senza collegarsi a nessuna IA.

Lavora come una piccola agenzia, in quattro passaggi:
1. l'analista legge le offerte e calcola i fatti (risparmio in euro, prezzi sotto l'euro,
   metà prezzo, risparmio totale della settimana, cene complete con i prodotti in offerta);
2. lo stratega sceglie l'idea della settimana (l'"angolo") tra quelle che i fatti permettono;
3. il copywriter scrive i testi per ogni canale nel tono del negozio, con frasi di un professionista;
4. il caporedattore rilegge: niente frasi fatte, niente prezzi che non esistono, al massimo
   un punto esclamativo, emoji solo dove il tono le ammette.

Regole che non si toccano: si usano solo prodotti e prezzi del volantino; i conti li fa il codice;
nessuna affermazione sul prodotto (fresco, locale, di giornata...) che il volantino non dica.
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from ...models import Flyer, Offer, Store
from ...money import discount_percent, find_prices, format_eur
from ...text_utils import normalize

# ------------------------------------------------------------------ parole e date

_GIORNI = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
_MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre",
         "ottobre", "novembre", "dicembre"]
_NUMERI = {2: "due", 3: "tre", 4: "quattro", 5: "cinque", 6: "sei", 7: "sette", 8: "otto", 9: "nove", 10: "dieci"}

TONES = ("familiare", "elegante", "giovane", "essenziale")


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
    if vt:
        return f"fino al {fmt_date(vt)}"
    return ""


def product_name(o: Offer, size: bool = True) -> str:
    """Come si scrive nei volantini italiani: prodotto, marca, formato ("Caffè in grani Lavazza 1 kg")."""
    name = f"{o.name} {o.brand}" if o.brand and o.brand.lower() not in o.name.lower() else o.name
    if size and o.description:
        name += f" {o.description}"
    return " ".join(name.split())


def said(o: Offer, size: bool = True) -> str:
    """Il nome dentro una frase: "spaghetti 500 g"; sigle e marche in testa restano come sono."""
    n = product_name(o, size)
    first = n.split(" ", 1)[0]
    if (len(first) > 1 and first.isupper()) or (o.brand and n.startswith(o.brand)):
        return n
    return n[:1].lower() + n[1:]


def per_unit(o: Offer) -> str:
    """ "al kg" per i prodotti a peso, altrimenti "a confezione"."""
    d = normalize(f"{o.description} {o.unit_price_text}")
    if re.search(r"\b(all etto|l etto|all hg|al hg)\b", d):
        return "all'etto"
    if re.search(r"\bal (kg|chilo)\b", d) or d.strip() in ("kg", "al kg"):
        return "al kg"
    if re.search(r"\bal (litro|l)\b", d):
        return "al litro"
    return "a confezione"


def saving(o: Offer) -> int:
    """Risparmio in centesimi su un pezzo (0 se il prezzo vecchio non è stampato)."""
    return max(0, (o.old_price_cents or 0) - o.price_cents)


def pct(o: Offer) -> int:
    """Sconto vero, calcolato dai prezzi (quello stampato può essere arrotondato a favore)."""
    return discount_percent(o.price_cents, o.old_price_cents) or o.discount_percent or 0


def join_it(parts: list[str]) -> str:
    parts = [p for p in parts if p]
    if len(parts) <= 1:
        return "".join(parts)
    return ", ".join(parts[:-1]) + " e " + parts[-1]


def featured_offers(flyer: Flyer, limit: int = 6) -> list[Offer]:
    feat = [o for o in flyer.offers if o.is_featured]
    rest = sorted((o for o in flyer.offers if not o.is_featured), key=lambda o: (-pct(o), -saving(o), o.price_cents))
    return (feat + rest)[:limit]


NON_FOOD = {"igiene casa", "cura persona", "animali", "infanzia", "altro"}


def hero_offer(offers: list[Offer]) -> Offer:
    """L'offerta su cui costruire la comunicazione: tra quelle in evidenza, lo sconto più forte.
    A parità quasi di sconto vince il cibo: è quello che fa venire voglia di entrare."""
    pool = [o for o in offers if o.is_featured] or offers
    return max(pool, key=lambda o: (pct(o) + min(saving(o), 300) / 30 + (0 if o.category in NON_FOOD else 10),
                                    -o.price_cents))


# ------------------------------------------------------------------ la conoscenza del mestiere

# Momenti d'uso reali per reparto: danno concretezza senza dire nulla di non verificabile sul prodotto.
MOMENTS = {
    "pasta e riso": ["per il pranzo di tutta la settimana", "per la pasta della domenica", "da avere sempre in dispensa"],
    "dispensa": ["da tenere in dispensa", "per fare scorta"],
    "colazione": ["per la colazione", "per cominciare bene la giornata"],
    "dolci e snack": ["per la merenda", "per la merenda dei ragazzi"],
    "pesce": ["per la cena del venerdì", "per un secondo leggero"],
    "carne": ["per il pranzo della domenica", "per la griglia del fine settimana", "per un secondo veloce"],
    "salumi e formaggi": ["per un tagliere senza pensieri", "per i panini della settimana", "per l'aperitivo in casa"],
    "latte e latticini": ["per tutta la famiglia", "da avere sempre in frigo"],
    "uova": ["per una cena veloce", "per i dolci del fine settimana"],
    "frutta e verdura": ["da mettere in tavola ogni giorno", "per la spesa di tutti i giorni"],
    "igiene casa": ["per fare scorta", "per la scorta del mese"],
    "cura persona": ["per fare scorta", "per la scorta del mese"],
    "bevande": ["per la tavola", "da tenere in frigo"],
    "vino e alcolici": ["per la cena con gli amici", "per l'aperitivo"],
    "surgelati": ["per le sere di fretta", "da tenere nel congelatore"],
    "pane e forno": ["per la tavola di tutti i giorni", "per la colazione"],
    "infanzia": ["per i più piccoli"],
    "animali": ["per i vostri animali"],
}

CATEGORY_EMOJI = {
    "frutta e verdura": "🍎", "carne": "🥩", "pesce": "🐟", "salumi e formaggi": "🧀", "latte e latticini": "🥛",
    "uova": "🥚", "pane e forno": "🥖", "pasta e riso": "🍝", "dispensa": "🥫", "surgelati": "❄️",
    "dolci e snack": "🍪", "colazione": "☕", "bevande": "🥤", "vino e alcolici": "🍷", "igiene casa": "🧽",
    "cura persona": "🧴", "infanzia": "🍼", "animali": "🐾", "altro": "🛒",
}

CATEGORY_TAG = {
    "frutta e verdura": "frutta", "carne": "macelleria", "pesce": "pesce", "salumi e formaggi": "formaggi",
    "latte e latticini": "latticini", "pane e forno": "pane", "pasta e riso": "pasta", "dispensa": "dispensa",
    "surgelati": "surgelati", "dolci e snack": "merenda", "colazione": "colazione", "bevande": "bevande",
    "vino e alcolici": "vino", "igiene casa": "casa", "cura persona": "curapersona", "infanzia": "bambini",
    "animali": "animali",
}


@dataclass(frozen=True)
class Recipe:
    """Una "cena" (o colazione, aperitivo...) che si compone con le offerte della settimana."""
    key: str
    title: str                    # "Pasta al pomodoro"
    the: str                      # con l'articolo, dentro una frase: "la pasta al pomodoro"
    occasion: str                 # "la cena", "la colazione"...
    slots: tuple[tuple[str, ...], ...]     # ogni slot: parole chiave; i primi due slot sono obbligatori
    min_items: int = 2


RECIPES = [
    Recipe("pomodoro", "Pasta al pomodoro", "la pasta al pomodoro", "la cena",
           (("spaghett", "penne", "fusill", "rigaton", "linguin", "maccheron", "tagliatell", "pasta", "mezze man"),
            ("passata", "pelati", "pomodor", "sugo", "polpa"),
            ("grana", "parmigian", "pecorino"), ("basilico",))),
    Recipe("carbonara", "Carbonara", "la carbonara", "la cena",
           (("spaghett", "rigaton", "mezze man", "pasta"), ("guanciale", "pancetta"),
            ("uova",), ("pecorino", "grana", "parmigian")), 3),
    Recipe("tagliere", "Tagliere per l'aperitivo", "il tagliere per l'aperitivo", "l'aperitivo",
           (("prosciutto", "salame", "mortadella", "bresaola", "speck", "coppa", "culatello"),
            ("formagg", "pecorino", "grana", "parmigian", "provolone", "asiago", "caciotta", "scamorza", "gorgonzola"),
            ("vino", "prosecco", "birra"), ("pane", "grissin", "taralli", "crackers", "focaccia"))),
    Recipe("colazione", "Colazione", "la colazione", "la colazione",
           (("caffe", "latte", "the ", "te ", "cappuccin", "orzo"),
            ("biscott", "fette biscottate", "cornett", "croissant", "merendin", "plumcake", "brioche", "cereali"),
            ("marmellat", "confettur", "miele", "crema spalmabile", "nutella"), ("succo",))),
    Recipe("pizza", "Pizza fatta in casa", "la pizza fatta in casa", "la cena del sabato",
           (("farina",), ("mozzarell", "fiordilatte", "fior di latte"), ("passata", "pomodor", "pelati", "polpa"),
            ("lievito",)), 3),
    Recipe("griglia", "Grigliata", "la grigliata", "il fine settimana",
           (("salsicc", "costin", "bistecc", "hamburger", "spiedin", "braciol", "pollo"),
            ("birra", "vino"), ("patate", "patatine"), ("pane",))),
    Recipe("pesce", "Cena di pesce", "la cena di pesce", "la cena",
           (("salmone", "orata", "spigola", "branzino", "merluzz", "gamber", "cozze", "vongole", "tonno", "pesce",
             "calamar", "polpo", "seppi"),
            ("vino bianco", "prosecco", "limon", "insalat", "patate"))),
    Recipe("risotto", "Risotto", "il risotto", "la cena",
           (("riso", "carnaroli", "arborio"), ("funghi", "zafferano", "grana", "parmigian", "burro", "zucca", "radicchio"),
            ("brodo", "dado", "vino bianco"))),
    Recipe("merenda", "Merenda", "la merenda", "la merenda",
           (("biscott", "merendin", "crackers", "cracker", "wafer", "cioccolat", "plumcake", "torta"),
            ("succo", "latte", "the freddo", "te freddo", "yogurt"))),
]


def _hay(o: Offer) -> str:
    return " " + normalize(f"{o.brand} {o.name} {o.description}") + " "


@dataclass
class Combo:
    recipe: Recipe
    items: list[Offer]
    total_cents: int

    @property
    def names(self) -> str:
        return join_it([said(o) for o in self.items])

    @property
    def saving_cents(self) -> int:
        return sum(saving(o) for o in self.items)


def find_combos(offers: list[Offer]) -> list[Combo]:
    """Le "ricette" che si possono comporre solo con prodotti in offerta, con il totale calcolato."""
    out = []
    for r in RECIPES:
        used: set[int] = set()
        items: list[Offer] = []
        for n, words in enumerate(r.slots):
            match = next((o for o in offers if id(o) not in used and any(w in _hay(o) for w in words)), None)
            if match is None:
                if n < 2:
                    items = []
                    break
                continue
            used.add(id(match))
            items.append(match)
        if len(items) >= max(2, r.min_items):
            out.append(Combo(r, items, sum(o.price_cents for o in items)))
    out.sort(key=lambda c: (-len(c.items), -c.saving_cents))
    return out


# ------------------------------------------------------------------ i fatti della settimana

@dataclass
class Facts:
    store: Store
    flyer: Flyer
    offers: list[Offer]               # le offerte su cui si costruisce la comunicazione (max 6-8)
    all_offers: list[Offer]
    hero: Offer
    tone: str
    validity: str
    where: str
    hours: str
    combos: list[Combo]
    under_euro: list[Offer]
    total_saving: int                 # risparmio prendendo un pezzo per ogni offerta in evidenza
    with_old_price: int
    weather: dict | None
    today: date

    @property
    def voi(self) -> bool:
        return self.tone == "elegante"

    @property
    def emoji_ok(self) -> bool:
        return self.tone in ("familiare", "giovane")


def gather_facts(store: Store, flyer: Flyer, offers: list[Offer] | None = None, weather: dict | None = None,
                 today: date | None = None) -> Facts:
    offers = list(offers if offers is not None else featured_offers(flyer))
    all_offers = list(flyer.offers) or offers
    tone = store.tone if store.tone in TONES else "familiare"
    hero = hero_offer(offers) if offers else None
    marked = [o for o in offers if saving(o) > 0]
    return Facts(
        store=store, flyer=flyer, offers=offers, all_offers=all_offers, hero=hero, tone=tone,
        validity=validity_text(flyer), where=", ".join(x for x in (store.address, store.city) if x),
        hours="; ".join(f"{k} {v}" for k, v in (store.opening_hours or {}).items()),
        combos=find_combos(all_offers), under_euro=[o for o in all_offers if o.price_cents < 100],
        total_saving=sum(saving(o) for o in marked), with_old_price=len(marked),
        weather=weather, today=today or date.today(),
    )


def computed_prices(f: Facts) -> set[int]:
    """Tutti gli importi che la redazione può scrivere: prezzi, prezzi vecchi, risparmi e totali calcolati."""
    allowed: set[int] = set()
    for o in f.all_offers:
        allowed.add(o.price_cents)
        if o.old_price_cents:
            allowed.update((o.old_price_cents, saving(o)))
    for c in f.combos:
        allowed.update((c.total_cents, c.saving_cents))
    allowed.add(f.total_saving)
    for o in f.all_offers:
        allowed.update(find_prices(o.unit_price_text or ""))
    allowed.update(find_prices(f.hours))     # orari come "8.30-13.00" non sono prezzi
    return allowed


# ------------------------------------------------------------------ l'idea della settimana

@dataclass
class Angle:
    kind: str                 # combo | half | saving | under_euro | hero
    hook: str                 # prima riga: deve far fermare il pollice
    detail: str = ""          # seconda riga: il perché, concreto
    combo: Combo | None = None
    featured: list[Offer] = field(default_factory=list)   # offerte già citate nel gancio


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def _price_with_old(o: Offer) -> str:
    return f"{format_eur(o.price_cents)} invece di {format_eur(o.old_price_cents)}" if o.old_price_cents \
        else format_eur(o.price_cents)


def _candidates(f: Facts) -> list[tuple[float, str]]:
    h = f.hero
    out: list[tuple[float, str]] = []
    if f.combos and len(f.combos[0].items) >= 3:
        c = f.combos[0]
        out.append((3.0 + len(c.items) * 0.4, "combo"))
    if h is not None and 45 <= pct(h) < 80 and h.old_price_cents:
        out.append((4.0, "half"))
    if h is not None and (saving(h) >= 100 or pct(h) >= 30):
        out.append((2.8 + min(saving(h), 500) / 500, "saving"))
    if len(f.under_euro) >= 3:
        out.append((2.4 + min(len(f.under_euro), 8) * 0.1, "under_euro"))
    out.append((1.0, "hero"))
    return sorted(out, reverse=True)


def choose_angle(f: Facts, rng: random.Random) -> Angle:
    """Sceglie l'idea tra le due migliori che i fatti permettono, variando da una settimana all'altra."""
    cands = _candidates(f)
    top = [k for _, k in cands[:2]]
    kind = top[0] if len(top) == 1 or rng.random() < 0.62 else top[1]
    return write_angle(f, kind, rng)


def write_angle(f: Facts, kind: str, rng: random.Random) -> Angle:
    h, voi, tone = f.hero, f.voi, f.tone
    tu = "vi" if voi else "ti"
    if kind == "combo" and f.combos:
        c = f.combos[0]
        total = format_eur(c.total_cents)
        if tone == "essenziale":
            hook = f"{c.recipe.title}: {total} in tutto, con le offerte della settimana."
        elif voi:
            options = [f"{c.recipe.title} con le offerte della settimana: {total} in tutto."]
            if normalize(c.recipe.occasion.split(" ", 1)[-1]) not in normalize(c.recipe.title):
                options.append(f"Per {c.recipe.occasion}, una proposta: {c.recipe.the} a {total} in tutto.")
            hook = rng.choice(options)
        else:
            options = [f"{c.recipe.title} con {total}: tutto in offerta questa settimana.",
                       f"Con {total} {tu} porti a casa {c.recipe.the}."]
            if normalize(c.recipe.occasion.split(" ", 1)[-1]) not in normalize(c.recipe.title):
                options.append(f"{c.recipe.title} per {c.recipe.occasion}: {total} in tutto.")
            hook = rng.choice(options)
        detail = f"{_cap(c.names)}: prezzi del volantino, " + ("sommati per voi." if voi else "già sommati.")
        if c.saving_cents >= 50:
            detail += f" Rispetto al prezzo pieno sono {format_eur(c.saving_cents)} in meno."
        return Angle("combo", hook, detail, combo=c, featured=list(c.items))
    if kind == "half" and h is not None:
        p = pct(h)
        how = "a metà prezzo" if 48 <= p <= 52 else ("a meno di metà prezzo" if p > 52 else "quasi a metà prezzo")
        hook = f"{product_name(h)} {how}: {_price_with_old(h)}."
        return Angle("half", hook, _moment_line(f, h, rng), featured=[h])
    if kind == "saving" and h is not None:
        sv = saving(h)
        if sv >= 100 and rng.random() < 0.6:
            hook = f"{product_name(h)}: {format_eur(sv)} in meno {per_unit(h)}, a {format_eur(h.price_cents)}."
        else:
            hook = f"{product_name(h)} a {_price_with_old(h)}."
        return Angle("saving", hook, _moment_line(f, h, rng), featured=[h])
    if kind == "under_euro" and len(f.under_euro) >= 3:
        items = sorted(f.under_euro, key=lambda o: (-pct(o), o.price_cents))[:4]
        n = _NUMERI.get(len(f.under_euro), str(len(f.under_euro)))
        hook = (f"{_cap(n)} prodotti sotto l'euro questa settimana." if tone != "essenziale"
                else f"Sotto l'euro: {n} prodotti.")
        detail = _cap(join_it([f"{said(o)} a {format_eur(o.price_cents)}" for o in items[:3]])) + "."
        return Angle("under_euro", hook, detail, featured=items[:3])
    # protagonista semplice
    hook = f"{product_name(h)} a {_price_with_old(h)}." if h is not None else ""
    if tone == "elegante" and h is not None:
        hook = f"Questa settimana vi proponiamo {said(h)} a {_price_with_old(h)}."
    return Angle("hero", hook, _moment_line(f, h, rng) if h is not None else "", featured=[h] if h else [])


def _moment_line(f: Facts, o: Offer, rng: random.Random) -> str:
    if f.tone == "essenziale":
        return ""
    w = weather_line(f)
    if w:
        return w
    moments = MOMENTS.get(o.category)
    if not moments:
        return ""
    m = rng.choice(moments)
    if f.voi and m.startswith("per "):
        return f"Pensato {m}."
    return f"{_cap(m)}."


def weather_line(f: Facts) -> str:
    """Se il meteo della settimana fa vendere un prodotto in offerta, lo si dice (con i dati veri)."""
    for a in ((f.weather or {}).get("advice") or []):
        try:
            d = date.fromisoformat(a["date"])
        except (KeyError, ValueError, TypeError):
            continue
        names = [x.get("name", "") for x in a.get("offers") or [] if x.get("name")]
        if not names:
            continue
        day = _cap(_GIORNI[d.weekday()])
        also = f"In offerta anche: {join_it([n[:1].lower() + n[1:] for n in names[:2]])}."
        sig = a.get("signal")
        if sig == "caldo" and a.get("tmax") is not None:
            return f"{day} sono previsti {round(a['tmax'])} °C. {also}"
        if sig == "freddo" and a.get("tmax") is not None:
            return f"{day} la massima non supera i {round(a['tmax'])} °C. {also}"
        if sig == "pioggia":
            return f"{day} è prevista pioggia. {also}"
    return ""


# ------------------------------------------------------------------ i testi per canale

def offer_row(o: Offer) -> str:
    row = f"{product_name(o)} · {format_eur(o.price_cents)}"
    if o.old_price_cents:
        row += f" (prima {format_eur(o.old_price_cents)})"
    if o.conditions:
        row += f", {o.conditions}"
    return row


def hashtags(f: Facts) -> list[str]:
    city = re.sub(r"\W", "", normalize(f.store.city or "").replace(" ", ""))
    lead = ([f.hero] if f.hero is not None else []) + [o for o in f.offers if o is not f.hero]
    cats = [CATEGORY_TAG[o.category] for o in lead[:3] if o.category in CATEGORY_TAG]
    tags = [*(f.store.hashtags or []), city, f"spesa{city}" if city else "", f"offerte{city}" if city else "",
            "volantino", "offertedellasettimana", *cats]
    seen, out = set(), []
    for t in tags:
        t = re.sub(r"[^\w]", "", t or "", flags=re.UNICODE)
        if t and t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out[:10]


def instagram(f: Facts, angle: Angle, rng: random.Random) -> str:
    lines = [angle.hook + (f" {CATEGORY_EMOJI.get((angle.featured or [f.hero])[0].category, '🛒')}"
                           if f.emoji_ok else "")]
    if angle.detail:
        lines.append(angle.detail)
    rest = [o for o in f.offers if o not in angle.featured][:4]
    if rest:
        intro = {"elegante": "Tra le altre proposte della settimana:", "essenziale": "Altre offerte:",
                 "giovane": rng.choice(["E poi:", "Nel volantino anche:"])}.get(
            f.tone, rng.choice(["Nel volantino trovi anche:", "E ancora:"]))
        lines += ["", intro, *(offer_row(o) for o in rest)]
    close = " · ".join(x for x in (f"Offerte valide {f.validity}" if f.validity else "", f.where) if x)
    if close:
        lines += ["", close]
    return "\n".join(lines)


def facebook(f: Facts, angle: Angle, rng: random.Random) -> str:
    s = f.store
    v = f", valido {f.validity}" if f.validity else ""
    opening = {
        "elegante": f"È disponibile il nuovo volantino di {s.name}{v}.",
        "essenziale": f"Volantino {s.name}{', ' + f.validity if f.validity else ''}.",
        "giovane": rng.choice([f"Volantino nuovo da {s.name}{v}.", f"È uscito il volantino di {s.name}{v}."]),
    }.get(f.tone, rng.choice([f"Da oggi trovi il nuovo volantino di {s.name}{v}.",
                              f"È arrivato il nuovo volantino di {s.name}{v}."]))
    parts = [opening, "", angle.hook]
    if angle.detail:
        parts.append(angle.detail)
    rest = [o for o in f.offers if o not in angle.featured]
    if rest:
        head = {"elegante": "Le altre offerte che abbiamo selezionato:", "essenziale": "Altre offerte:"}.get(
            f.tone, "Le altre offerte da segnare:")
        parts += ["", head, *(offer_row(o) for o in rest)]
    # un secondo spunto concreto, diverso dall'idea principale
    extra = ""
    if angle.kind != "combo" and f.combos:
        c = f.combos[0]
        idea = (f"Un'idea per {c.recipe.occasion}, {c.recipe.the}"
                if normalize(c.recipe.occasion.split(" ", 1)[-1]) not in normalize(c.recipe.title)
                else f"Un'idea: {c.recipe.the}")
        extra = (f"{idea}: {c.names}. "
                 f"Con i prezzi del volantino fanno {format_eur(c.total_cents)} in tutto.")
    elif f.with_old_price >= 3 and f.total_saving >= 200:
        extra = (f"Prendendo un pezzo per ciascuna delle {f.with_old_price} offerte qui sopra con il prezzo barrato "
                 f"{'risparmiate' if f.voi else 'risparmi'} {format_eur(f.total_saving)}.")
    if extra and f.tone != "essenziale":
        parts += ["", extra]
    tail = []
    if f.where:
        tail.append(f.where + "." if f.tone == "essenziale" else
                    ("Vi aspettiamo in " if f.voi else "Ti aspettiamo in ") + f.where + ".")
    if f.hours:
        tail.append(f"Orari: {f.hours}.")
    if tail:
        parts += ["", *tail]
    return "\n".join(parts)


# ------------------------------------------------------------------ il caporedattore

BANNED = [
    "imperdibil", "non perdere", "non lasciart", "scopri", "che aspetti", "affrettati", "corri",
    "occasione unica", "delizi", "gusto unico", "sapori autentici", "viaggio", "esperienza",
    "qualità superiore", "il meglio per te", "merita il meglio", "risparmio garantito", "irresistibil",
    "coccol", "a portata di mano", "a prezzi imbattibili", "prezzi pazzi", "super offert", "mega",
    "tutto questo e molto altro", "e tanto altro", "sei pronto", "siete pronti", "lasciati",
    "concediti", "regalati", "immergiti", "esplora", "ti aspettano tante", "fantastic", "incredibil",
    "straordinari", "eccezional", "pazzesc", "top!", "wow",
]

_EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF☀-➿]")


def review(text: str, allowed: set[int], tone: str) -> list[str]:
    """I difetti di un testo: frasi fatte, prezzi non veri, troppi ! o emoji, tono sbagliato."""
    issues = []
    low = text.lower()
    issues += [f"frase fatta «{b}»" for b in BANNED if b in low]
    if "—" in text:
        issues.append("trattino lungo")
    if text.count("!") > 1:
        issues.append("troppi punti esclamativi")
    emoji = _EMOJI_RE.findall(text)
    if tone in ("elegante", "essenziale") and emoji:
        issues.append("emoji con un tono che non le ammette")
    elif len(emoji) > 2:
        issues.append("troppe emoji")
    wrong = [p for p in find_prices(text) if p not in allowed]
    if wrong:
        issues.append("prezzo non presente nel volantino: " + ", ".join(format_eur(p) for p in wrong))
    if tone == "elegante" and re.search(r"\b(ti|tuo|tua|trovi|aspettiamo te)\b", low):
        issues.append("dà del tu con il tono elegante")
    return issues


def _clean(text: str, tone: str) -> str:
    if tone in ("elegante", "essenziale"):
        text = _EMOJI_RE.sub("", text).replace("️", "")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r" {2,}", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


# ------------------------------------------------------------------ il lavoro completo

@dataclass
class Written:
    texts: dict[str, dict]
    angle: Angle | None
    facts: Facts
    issues: list[str]


STRATEGY = {
    "combo": "Una cena completa con i prodotti in offerta, con il totale già calcolato.",
    "half": "Il prodotto con lo sconto più forte: metà prezzo, detto con i numeri.",
    "saving": "Il risparmio in euro sul prodotto protagonista.",
    "under_euro": "I prodotti sotto l'euro: una ragione semplice per entrare.",
    "occasion": "La ricorrenza della settimana, con i prodotti del volantino che la accompagnano.",
    "fresh": "Il reparto fresco della settimana: più offerte nello stesso banco.",
    "stock": "Le offerte da scorta: prodotti che si comprano oggi e si usano per settimane.",
    "weekend": "Il fine settimana: cosa portare in tavola sabato e domenica.",
    "basket": "Tre prodotti di reparti diversi, con il totale già sommato.",
    "total": "Il risparmio complessivo della settimana, calcolato offerta per offerta.",
    "hero": "Il prodotto protagonista e il suo prezzo.",
}


def write_week(store: Store, flyer: Flyer, offers: list[Offer] | None = None, weather: dict | None = None,
               today: date | None = None, seed: int | None = None, history: list[dict] | None = None,
               avoid: set[str] | None = None, version: int = 0) -> Written:
    """Scrive Instagram, Facebook e la didascalia per Reel e TikTok della settimana.

    history: cosa è già uscito per questo negozio nelle settimane scorse (la redazione non si ripete);
    avoid: idee da non riproporre ("Un'altra idea"); version: cambia le formulazioni a parità di volantino.
    """
    from . import editor
    f = gather_facts(store, flyer, offers, weather, today)
    tags = hashtags(f)
    if not f.offers:
        empty = f"Le offerte di {store.name}" + (f", {f.validity}" if f.validity else "") + "."
        return Written({"instagram": {"title": "Post Instagram", "body": empty, "meta": {"hashtags": tags}},
                        "facebook": {"title": "Post Facebook", "body": empty, "meta": {}},
                        "reel": {"title": "Didascalia per Reel e TikTok", "body": empty, "meta": {}}}, None, f, [])
    base = seed if seed is not None else (flyer.id or 0) * 7919 + (store.id or 0)
    rng = random.Random(base + version * 104729 + TONES.index(f.tone) * 31)
    history = history or []
    used = set()
    for past in history[:6]:
        used.update(v for k, v in past.items() if k in ("hook_id", "layout", "intro", "close", "opener") and v)
    said_before = {normalize(p.get("hook", "")) for p in history if p.get("hook")}
    allowed = computed_prices(f)
    best = None
    for idea in editor.choose(f, history, rng, avoid)[:6]:
        d = editor.draft(f, idea, rng, used, said_before)
        ig, ig_meta = editor.instagram(f, d, rng, used)
        fb, fb_meta = editor.facebook(f, d, rng, used)
        ig, fb = _clean(ig, f.tone), _clean(fb, f.tone)
        issues = review(ig, allowed, f.tone) + review(fb, allowed, f.tone)
        if best is None or len(issues) < len(best[4]):
            best = (d, ig, fb, {**ig_meta, **fb_meta}, issues)
        if not issues:
            break
    d, ig, fb, ids, issues = best
    combo = next((c for c in f.combos if list(c.items) == d.featured), None) if d.kind == "combo" else None
    angle = Angle(d.kind, d.hook, d.detail, combo=combo, featured=d.featured)
    meta = {"hashtags": tags, "strategy": STRATEGY.get(d.kind, ""), "angle": d.kind, "hero": d.meta.get("hero", ""),
            "hook_id": d.hook_id, "hook": d.hook, "version": version, **ids}
    reel = _clean(editor.reel_caption(f, d, tags), f.tone)
    return Written({
        "instagram": {"title": "Post Instagram", "body": ig, "meta": meta},
        "facebook": {"title": "Post Facebook", "body": fb, "meta": {"angle": d.kind}},
        "reel": {"title": "Didascalia per Reel e TikTok", "body": reel, "meta": {"angle": d.kind}},
    }, angle, f, issues)


# ------------------------------------------------------------------ cosa filmare al banco

SHOOT_IDEAS = {
    "pesce": "Il banco del pesce mentre servi un cliente: 10-15 secondi, telefono in verticale.",
    "carne": "Il banco della macelleria mentre tagli o prepari un pezzo: 10-15 secondi.",
    "frutta e verdura": "Le cassette del reparto ortofrutta, riprese da vicino, muovendoti piano lungo il banco.",
    "salumi e formaggi": "L'affettatrice al banco gastronomia, da vicino: bastano 10 secondi.",
    "pane e forno": "Il pane sugli scaffali o appena sfornato, ripreso da vicino.",
    "latte e latticini": "Il frigo dei freschi con i prodotti in offerta in primo piano.",
}


def shoot_ideas(f: Facts, angle: Angle | None) -> list[str]:
    """Due o tre riprese da fare col telefono, per il Reel dal banco."""
    ideas: list[str] = []
    seen: set[str] = set()
    for o in f.offers:
        idea = SHOOT_IDEAS.get(o.category)
        if idea and o.category not in seen:
            seen.add(o.category)
            ideas.append(f"{idea} Prodotto in offerta: {product_name(o, False)}.")
    if angle is not None and angle.combo is not None:
        c = angle.combo
        ideas.insert(0, f"I prodotti di «{c.recipe.title}» uno accanto all'altro sul bancone ({c.names}): "
                        "una ripresa lenta da sinistra a destra.")
    return ideas[:3]


def week_dates(flyer: Flyer, today: date | None = None) -> tuple[date, date]:
    start = flyer.valid_from or today or date.today()
    end = flyer.valid_to or start + timedelta(days=6)
    if end < start:
        end = start + timedelta(days=6)
    return start, end
