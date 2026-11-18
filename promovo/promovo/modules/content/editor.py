"""La redazione di Promovo, seconda edizione: idee diverse ogni settimana e mai la stessa frase.

Come lavora una brava redazione di un'agenzia:
1. guarda i fatti della settimana (calcolati dal codice: risparmi, sotto l'euro, metà prezzo, cene
   complete, ricorrenze del calendario, reparti freschi, fine settimana, scorte);
2. ricorda cosa ha già pubblicato per quel negozio nelle settimane precedenti (idea, prodotto
   protagonista, frasi usate) e non si ripete;
3. sceglie l'idea migliore tra quelle nuove, la scrive con una delle tante formulazioni possibili
   nel tono del negozio e con una struttura diversa (elenco, frase, testo breve);
4. il caporedattore rilegge (writer.review): niente frasi fatte, solo prezzi veri, tu/voi giusto.

Niente viene inventato: ogni numero viene dal volantino o da un calcolo; le ricorrenze sono date vere.
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from datetime import timedelta

from ...models import Offer
from ...money import format_eur
from ...text_utils import normalize
from .calendar import Occasion, occasions_in
from .writer import (CATEGORY_EMOJI, MOMENTS, Combo, Facts, _cap, _GIORNI, fmt_date, join_it, pct, per_unit,
                     product_name, said, saving, week_dates, weather_line)

FRESH = {"pesce": "pescheria", "carne": "macelleria", "frutta e verdura": "ortofrutta",
         "salumi e formaggi": "gastronomia", "pane e forno": "forno"}
FRESH_THE = {"pescheria": "la pescheria", "macelleria": "la macelleria", "ortofrutta": "l'ortofrutta",
             "gastronomia": "la gastronomia", "forno": "il forno"}
FOOD_OCCASIONS = {"pasqua", "pasquetta", "natale", "capodanno", "carnevale", "ferragosto"}
WEEKEND_CATS = {"carne", "bevande", "vino e alcolici", "dolci e snack", "salumi e formaggi", "pesce"}
STOCK_CATS = {"dispensa", "pasta e riso", "igiene casa", "cura persona", "bevande", "colazione", "infanzia", "animali"}
PERISHABLE = {"carne", "pesce", "frutta e verdura", "latte e latticini", "uova", "pane e forno", "salumi e formaggi",
              "surgelati"}
_MULTI = re.compile(r"\b\d+\s?x\b|\bconf\b|\bfamiglia\b|\bmaxi\b|\bscorta\b|\b\d+\s?(pezzi|rotoli|lavaggi|capsule)\b", re.I)


@dataclass
class Idea:
    kind: str
    score: float
    featured: list[Offer]
    data: dict = field(default_factory=dict)
    hero: str = ""                    # prodotto protagonista (per non ripeterlo nelle settimane dopo)


@dataclass
class Draft:
    kind: str
    hook: str
    detail: str
    featured: list[Offer]
    hook_id: str
    meta: dict = field(default_factory=dict)


def _p(o: Offer) -> str:
    return format_eur(o.price_cents)


def _po(o: Offer) -> str:
    return f"{format_eur(o.price_cents)} invece di {format_eur(o.old_price_cents)}" if o.old_price_cents else _p(o)


def _pair(o: Offer) -> str:
    return f"{said(o)} a {_p(o)}"


# ------------------------------------------------------------------ 1. le idee possibili

def ideas(f: Facts) -> list[Idea]:
    out: list[Idea] = []
    h = f.hero
    pool = f.all_offers or f.offers
    start, end = week_dates(f.flyer, f.today)
    # ricorrenze con prodotti in volantino
    for occ in occasions_in(start, end):
        def rank(o: Offer) -> int:
            hay = " " + normalize(f"{o.name} {o.brand} {o.description}")
            return min((i for i, w in enumerate(occ.words) if w in hay), default=99)
        match = [o for o in pool if rank(o) < 99]
        if match:
            match.sort(key=lambda o: (rank(o), -pct(o)))
            near = start <= occ.day <= end + timedelta(days=2)       # la ricorrenza cade proprio in questi giorni
            out.append(Idea("occasion", 4.3 + (0.9 if near else 0.0), match[:3], {"occ": occ}, hero=match[0].name))
    if f.combos and len(f.combos[0].items) >= 3:
        c = f.combos[0]
        out.append(Idea("combo", 3.0 + 0.4 * len(c.items), list(c.items), {"combo": c}, hero=c.recipe.key))
    for c in f.combos[1:2]:
        if len(c.items) >= 3:
            out.append(Idea("combo", 2.6 + 0.3 * len(c.items), list(c.items), {"combo": c}, hero=c.recipe.key))
    if h is not None and 45 <= pct(h) < 80 and h.old_price_cents:
        out.append(Idea("half", 4.0, [h], hero=h.name))
    if h is not None and (saving(h) >= 100 or pct(h) >= 30):
        out.append(Idea("saving", 2.8 + min(saving(h), 500) / 500, [h], hero=h.name))
    # un secondo protagonista possibile: lo sconto più forte dopo quello principale
    others = sorted((o for o in f.offers if o is not h and o.old_price_cents), key=lambda o: (-pct(o), -saving(o)))
    if others and (pct(others[0]) >= 25 or saving(others[0]) >= 80):
        out.append(Idea("saving", 2.4 + min(saving(others[0]), 500) / 600, [others[0]], hero=others[0].name))
    if len(f.under_euro) >= 3:
        items = sorted(f.under_euro, key=lambda o: (-pct(o), o.price_cents))
        out.append(Idea("under_euro", 2.4 + min(len(f.under_euro), 8) * 0.1, items[:3], {"n": len(f.under_euro)},
                        hero="sotto-euro"))
    by_dept: dict[str, list[Offer]] = {}
    for o in pool:
        if o.category in FRESH:
            by_dept.setdefault(o.category, []).append(o)
    for cat, items in by_dept.items():
        if len(items) >= 3:
            items.sort(key=lambda o: (-pct(o), o.price_cents))
            out.append(Idea("fresh", 2.7 + 0.15 * min(len(items), 6), items[:3], {"dept": FRESH[cat], "n": len(items)},
                            hero="reparto-" + cat))
    stock = [o for o in pool if pct(o) >= 20 and o.category not in PERISHABLE
             and (o.category in STOCK_CATS or _MULTI.search(f"{o.name} {o.description}"))]
    if len(stock) >= 2:
        stock.sort(key=lambda o: (-pct(o), -saving(o)))
        out.append(Idea("stock", 2.5, stock[:2], hero="scorta"))
    weekend = any((start + timedelta(days=i)).weekday() >= 5 for i in range((end - start).days + 1))
    wk = [o for o in pool if o.category in WEEKEND_CATS]
    if weekend and len(wk) >= 2:
        wk.sort(key=lambda o: (-pct(o), -saving(o)))
        out.append(Idea("weekend", 2.3, wk[:2], hero="weekend"))
    basket = _basket(pool)
    if basket:
        out.append(Idea("basket", 2.2, basket, {"total": sum(o.price_cents for o in basket)}, hero="cestino"))
    if f.with_old_price >= 4 and f.total_saving >= 400:
        out.append(Idea("total", 2.1, [], {"n": f.with_old_price, "tot": f.total_saving}, hero="risparmio-totale"))
    if h is not None:
        out.append(Idea("hero", 1.0, [h], hero=h.name))
    return out


def _basket(pool: list[Offer]) -> list[Offer]:
    """Tre prodotti di reparti diversi che insieme costano poco (sotto i 5 o i 10 euro)."""
    picked, cats = [], set()
    for o in sorted(pool, key=lambda o: (-pct(o), o.price_cents)):
        if o.category in cats or o.price_cents > 400:
            continue
        picked.append(o)
        cats.add(o.category)
        if len(picked) == 3:
            break
    if len(picked) == 3 and sum(o.price_cents for o in picked) <= 1000:
        return picked
    return []


# ------------------------------------------------------------------ 2. scegliere senza ripetersi

def choose(f: Facts, history: list[dict], rng: random.Random, avoid: set[str] | None = None) -> list[Idea]:
    """Le idee in ordine di preferenza, tenendo conto di cosa è già uscito nelle settimane scorse."""
    avoid = avoid or set()
    scored = []
    for k, idea in enumerate(ideas(f)):
        s = idea.score + rng.uniform(0, 0.6)
        for age, past in enumerate(history[:4]):
            weight = (2.6, 1.4, 0.8, 0.4)[age]
            if past.get("angle") == idea.kind:
                s -= weight
            if idea.hero and past.get("hero") == idea.hero:
                s -= weight * 1.2
        if idea.kind in avoid or f"{idea.kind}:{idea.hero}" in avoid:
            s -= 10
        scored.append((s, k, idea))
    scored.sort(key=lambda t: (-t[0], t[1]))
    return [i for _, _, i in scored]


def _pick(rng: random.Random, options: list[tuple[str, str]], used: set[str]) -> tuple[str, str]:
    """Una formulazione (id, testo) non usata di recente, se ce n'è una."""
    fresh = [o for o in options if o[0] not in used and o[1]]
    pool = fresh or [o for o in options if o[1]]
    return rng.choice(pool)


# ------------------------------------------------------------------ 3. scrivere l'idea

def _occ_when(occ: Occasion) -> str:
    """ "Pasqua è domenica 5 aprile." (solo per le ricorrenze con una data precisa)."""
    if occ.key in ("estate", "scuola"):
        return ""
    return f"{_cap(occ.the)} è {_GIORNI[occ.day.weekday()]} {fmt_date(occ.day)}."


def draft(f: Facts, idea: Idea, rng: random.Random, used: set[str], said_before: set[str] | None = None) -> Draft:
    tone = f.tone
    g = "voi" if f.voi else ("ess" if tone == "essenziale" else "tu")
    k = idea.kind
    o = idea.featured[0] if idea.featured else f.hero
    opts: list[tuple[str, str]] = []
    detail = ""
    if k == "occasion":
        occ: Occasion = idea.data["occ"]
        to = f"verso {occ.the}" if occ.article else f"verso {occ.name}"
        opts = {
            "tu": [("occ1", f"{_cap(to)}: {_pair(o)}."), ("occ2", f"Per {occ.the}, {said(o)} a {_po(o)}."),
                   ("occ3", f"Si avvicina {occ.the}: in volantino {_pair(o)}."),
                   ("occ4", f"{_cap(occ.the)} in tavola: {_pair(o)}." if occ.key in FOOD_OCCASIONS else "")],
            "voi": [("occv1", f"Per {occ.the} vi proponiamo {said(o)} a {_po(o)}."),
                    ("occv2", f"{_cap(to)}: {said(o)} a {_po(o)}.")],
            "ess": [("occe1", f"{_cap(occ.the)}: {product_name(o)} {_p(o)}.")],
        }[g]
        when = _occ_when(occ)
        rest = [x for x in idea.featured[1:3]]
        detail = when + (" " if when and rest else "") + (f"In volantino anche {join_it([_pair(x) for x in rest])}." if rest else "")
    elif k == "combo":
        c: Combo = idea.data["combo"]
        tot = format_eur(c.total_cents)
        opts = {
            "tu": [("cb1", f"{c.recipe.title} con {tot}: tutto in offerta questa settimana."),
                   ("cb2", f"Con {tot} ti porti a casa {c.recipe.the}."),
                   ("cb3", f"Stasera {c.recipe.the}: {tot} con i prezzi del volantino."),
                   ("cb4", f"{_cap(c.recipe.the)} della settimana costa {tot}."),
                   ("cb5", f"Idea per {c.recipe.occasion}: {c.recipe.the}, {tot} in tutto.")],
            "voi": [("cbv1", f"{c.recipe.title} con le offerte della settimana: {tot} in tutto."),
                    ("cbv2", f"Per {c.recipe.occasion} vi suggeriamo {c.recipe.the}: {tot} in tutto.")],
            "ess": [("cbe1", f"{c.recipe.title}: {tot} in tutto, con le offerte della settimana.")],
        }[g]
        if normalize(c.recipe.occasion.split(" ", 1)[-1]) in normalize(c.recipe.title):
            opts = [x for x in opts if c.recipe.occasion not in x[1] or x[0] in ("cb5",)] or opts
            opts = [x for x in opts if x[0] not in ("cb5", "cbv2")] or opts
        detail = f"{_cap(c.names)}: " + ("prezzi del volantino, sommati per voi." if f.voi else "prezzi del volantino, già sommati.")
        if c.saving_cents >= 50:
            detail += f" Rispetto al prezzo pieno sono {format_eur(c.saving_cents)} in meno."
    elif k == "half":
        p = pct(o)
        how = "a metà prezzo" if 48 <= p <= 52 else ("a meno di metà prezzo" if p > 52 else "quasi a metà prezzo")
        opts = {
            "tu": [("hf1", f"{product_name(o)} {how}: {_po(o)}."),
                   ("hf2", f"{_cap(how)}, questa settimana: {said(o)} a {_p(o)}."),
                   ("hf3", f"{product_name(o)}: da {format_eur(o.old_price_cents)} a {_p(o)}.")],
            "voi": [("hfv1", f"{product_name(o)} {how}: {_po(o)}."),
                    ("hfv2", f"Questa settimana {said(o)} è {how}: {_p(o)}.")],
            "ess": [("hfe1", f"{product_name(o)} {_p(o)} (prima {format_eur(o.old_price_cents)}), -{p}%.")],
        }[g]
        detail = _detail_for(f, o, rng)
    elif k == "saving":
        sv = format_eur(saving(o))
        opts = {
            "tu": [("sv1", f"{product_name(o)} a {_po(o)}."),
                   ("sv2", f"{product_name(o, per_unit(o) == 'a confezione')}: {sv} in meno {per_unit(o)}, a {_p(o)}."),
                   ("sv3", f"Questa settimana a {_p(o)}: {said(o)}, prima {format_eur(o.old_price_cents)}."),
                   ("sv4", f"Il prezzo della settimana: {said(o)} a {_p(o)}."),
                   ("sv5", f"{_p(o)} per {said(o)}, invece di {format_eur(o.old_price_cents)}."
                    if per_unit(o) == "a confezione" else "")],
            "voi": [("svv1", f"Questa settimana vi proponiamo {said(o)} a {_po(o)}."),
                    ("svv2", f"{product_name(o)}: da {format_eur(o.old_price_cents)} a {_p(o)}."),
                    ("svv3", f"{product_name(o)} a {_p(o)}, {sv} in meno rispetto al prezzo pieno.")],
            "ess": [("sve1", f"{product_name(o)}: {_p(o)} (prima {format_eur(o.old_price_cents)})."),
                    ("sve2", f"{product_name(o)} {_p(o)}, -{pct(o)}%.")],
        }[g]
        detail = _detail_for(f, o, rng)
    elif k == "under_euro":
        n = idea.data["n"]
        from .writer import _NUMERI
        nn = _NUMERI.get(n, str(n))
        three = join_it([_pair(x) for x in idea.featured])
        opts = {
            "tu": [("ue1", f"{_cap(nn)} prodotti sotto l'euro questa settimana."),
                   ("ue2", f"Con meno di un euro: {three}."),
                   ("ue3", f"{_cap(nn)} cose che costano meno di un euro, tutte in volantino.")],
            "voi": [("uev1", f"Questa settimana {nn} prodotti costano meno di un euro."),
                    ("uev2", f"Sotto l'euro, questa settimana: {three}.")],
            "ess": [("uee1", f"Sotto l'euro: {nn} prodotti.")],
        }[g]
        detail = _cap(three) + "."
    elif k == "fresh":
        dept, n = idea.data["dept"], idea.data["n"]
        from .writer import _NUMERI
        nn = _NUMERI.get(n, str(n))
        three = join_it([_pair(x) for x in idea.featured])
        opts = {
            "tu": [("fr1", f"Dal reparto {dept}: {nn} prodotti in offerta questa settimana."),
                   ("fr2", f"Questa settimana {FRESH_THE[dept]} è in volantino: {three}."),
                   ("fr3", f"{_cap(dept)}, le offerte della settimana: {three}.")],
            "voi": [("frv1", f"Dal reparto {dept}, {nn} proposte in offerta questa settimana."),
                    ("frv2", f"{_cap(FRESH_THE[dept])} della settimana: {three}.")],
            "ess": [("fre1", f"{_cap(dept)}: {three}.")],
        }[g]
        detail = (_cap(three) + ".") if not any(three in t for _, t in opts) else _detail_for(f, idea.featured[0], rng)
    elif k == "stock":
        a, b = idea.featured[0], idea.featured[1]
        opts = {
            "tu": [("st1", f"Settimana buona per fare scorta: {_pair(a)} e {_pair(b)}."),
                   ("st2", f"Da tenere in casa: {said(a)} a {_po(a)}."),
                   ("st3", f"Per la scorta di casa: {_pair(a)}, {_pair(b)}.")],
            "voi": [("stv1", f"Una settimana conveniente per la scorta: {_pair(a)} e {_pair(b)}.")],
            "ess": [("ste1", f"Scorte: {product_name(a)} {_p(a)}, {product_name(b)} {_p(b)}.")],
        }[g]
        detail = _detail_for(f, a, rng)
    elif k == "weekend":
        a, b = idea.featured[0], idea.featured[1]
        opts = {
            "tu": [("wk1", f"Per il fine settimana: {_pair(a)} e {_pair(b)}."),
                   ("wk2", f"Sabato e domenica in tavola: {_pair(a)}, {_pair(b)}."),
                   ("wk3", f"Il fine settimana costa meno: {_pair(a)}.")],
            "voi": [("wkv1", f"Per il vostro fine settimana: {_pair(a)} e {_pair(b)}.")],
            "ess": [("wke1", f"Fine settimana: {product_name(a)} {_p(a)}, {product_name(b)} {_p(b)}.")],
        }[g]
        detail = _detail_for(f, a, rng)
    elif k == "basket":
        tot = format_eur(idea.data["total"])
        three = join_it([said(x) for x in idea.featured])
        opts = {
            "tu": [("bk1", f"Tre prodotti, {tot} in tutto: {three}."),
                   ("bk2", f"Con {tot} prendi {three}."),
                   ("bk3", f"{tot} per tre: {three}, tutti in offerta.")],
            "voi": [("bkv1", f"Con {tot}: {three}, tutti in offerta questa settimana.")],
            "ess": [("bke1", f"{three}: {tot} in tutto.")],
        }[g]
        detail = _cap(join_it([_pair(x) for x in idea.featured])) + "."
    elif k == "total":
        n, tot = idea.data["n"], format_eur(idea.data["tot"])
        opts = {
            "tu": [("tt1", f"{n} offerte con il prezzo barrato: prendendone una di ciascuna risparmi {tot}."),
                   ("tt2", f"{tot} di risparmio sul prezzo pieno, se prendi una confezione di ognuna di queste {n} offerte.")],
            "voi": [("ttv1", f"Prendendo una confezione per ciascuna di queste {n} offerte risparmiate {tot}.")],
            "ess": [("tte1", f"{n} offerte, {tot} di risparmio complessivo sul prezzo pieno.")],
        }[g]
        detail = ""
    else:   # protagonista
        opts = {
            "tu": [("hr1", f"{product_name(o)} a {_po(o)}."), ("hr2", f"In evidenza questa settimana: {_pair(o)}."),
                   ("hr3", f"Il prodotto della settimana: {said(o)}, {_po(o)}.")],
            "voi": [("hrv1", f"Questa settimana vi proponiamo {said(o)} a {_po(o)}."),
                    ("hrv2", f"La nostra proposta della settimana: {said(o)}, {_po(o)}.")],
            "ess": [("hre1", f"{product_name(o)}: {_po(o)}.")],
        }[g]
        detail = _detail_for(f, o, rng)
    if tone == "giovane" and o is not None:
        end = f"fino al {fmt_date(f.flyer.valid_to)}" if f.flyer.valid_to else "questa settimana"
        quick = {"saving": [("g-sv1", f"{_cap(said(o))}: {_p(o)}. Prima {format_eur(o.old_price_cents)}." if o.old_price_cents else ""),
                            ("g-sv2", f"{_p(o)} e {said(o)} è tuo, {end}." if per_unit(o) == "a confezione" else "")],
                 "hero": [("g-hr1", f"{_cap(said(o))}, {_p(o)}. Fino a esaurimento scorte, {end}.")],
                 "half": [("g-hf1", f"Metà prezzo, {end}: {said(o)} a {_p(o)}.")],
                 "weekend": [("g-wk1", f"Weekend in arrivo: {_pair(o)}.")]}.get(k, [])
        opts = [x for x in quick if x[1]] + opts
    said_before = said_before or set()
    opts = [x for x in opts if x[1] and normalize(x[1]) not in said_before] or opts    # mai la stessa frase
    hook_id, hook = _pick(rng, opts, used)
    featured = list(idea.featured) if idea.featured else ([o] if o is not None else [])
    return Draft(k, hook, detail, featured, hook_id, {"hero": idea.hero})


def _detail_for(f: Facts, o: Offer | None, rng: random.Random) -> str:
    """La seconda riga: un fatto in più (meteo, prezzo al kg, momento d'uso, ricorrenza)."""
    if o is None:
        return ""
    options = []
    w = weather_line(f)
    if w:
        options.append(w)
    if o.unit_price_text and f.tone != "essenziale":
        options.append(f"Fanno {o.unit_price_text}.")
    m = MOMENTS.get(o.category)
    if m and f.tone != "essenziale":
        mom = rng.choice(m)
        options.append(f"Pensato {mom}." if f.voi and mom.startswith("per ") else f"{_cap(mom)}.")
    start, end = week_dates(f.flyer, f.today)
    for occ in occasions_in(start, end)[:1]:
        when = _occ_when(occ)
        if when:
            options.append(when)
    return rng.choice(options) if options else ""


# ------------------------------------------------------------------ 4. i testi per canale, con strutture diverse

def _row(o: Offer) -> str:
    row = f"{product_name(o)} · {_p(o)}"
    if o.old_price_cents:
        row += f" (prima {format_eur(o.old_price_cents)})"
    if o.conditions:
        row += f", {o.conditions}"
    return row


def instagram(f: Facts, d: Draft, rng: random.Random, used: set[str]) -> tuple[str, dict]:
    emoji = ""
    if f.emoji_ok and d.featured and d.featured[0].category in CATEGORY_EMOJI and d.featured[0].category != "altro":
        emoji = " " + CATEGORY_EMOJI[d.featured[0].category]
    lines = [d.hook + emoji]
    if d.detail and d.detail not in d.hook:
        lines.append(d.detail)
    rest = [o for o in f.offers if o not in d.featured][:4]
    layout_id, _ = _pick(rng, [("L-list", "x"), ("L-inline", "x"), ("L-short", "x" if len(rest) <= 2 else "")], used)
    if rest and layout_id == "L-list":
        intro_id, intro = _pick(rng, {
            "voi": [("i-v1", "Tra le altre proposte della settimana:"), ("i-v2", "Le altre offerte selezionate:")],
            "ess": [("i-e1", "Altre offerte:")],
        }.get("voi" if f.voi else ("ess" if f.tone == "essenziale" else ""), [
            ("i1", "Nel volantino trovi anche:"), ("i2", "E ancora:"), ("i3", "Da segnare anche:"),
            ("i4", "Altre offerte della settimana:")]), used)
        lines += ["", intro, *(_row(o) for o in rest)]
    elif rest and layout_id in ("L-inline", "L-short"):
        intro_id = "inline"
        lead = "Nel volantino anche " if f.voi else rng.choice(["In volantino anche ", "Da segnare anche ", "E poi "])
        if "volantino anche" in (d.detail + d.hook) and "volantino anche" in lead:
            lead = "Da segnare anche " if not f.voi else "Tra le altre proposte, "
        lines += ["", lead + join_it([_pair(o) for o in rest[:3]]) + "."]
    else:
        intro_id = ""
    close_opts = [("c1", " · ".join(x for x in (f"Offerte valide {f.validity}" if f.validity else "", f.where) if x))]
    if f.flyer.valid_to and f.where:
        close_opts.append(("c2", f"Fino al {fmt_date(f.flyer.valid_to)}, in {f.where}."))
        if not f.voi and f.tone != "essenziale":
            close_opts.append(("c3", f"Ti aspettiamo in {f.where}, fino al {fmt_date(f.flyer.valid_to)}."))
        if f.voi:
            close_opts.append(("c4", f"Vi aspettiamo in {f.where}, fino al {fmt_date(f.flyer.valid_to)}."))
    close_id, close = _pick(rng, close_opts, used)
    if close:
        lines += ["", close]
    return "\n".join(lines), {"layout": layout_id, "intro": intro_id, "close": close_id}


def facebook(f: Facts, d: Draft, rng: random.Random, used: set[str]) -> tuple[str, dict]:
    s = f.store
    v = f", valido {f.validity}" if f.validity else ""
    opener_id, opener = _pick(rng, {
        "voi": [("o-v1", f"È disponibile il nuovo volantino di {s.name}{v}."),
                ("o-v2", f"Il volantino di {s.name} di questa settimana{v}."),
                ("o-v3", f"Da oggi in negozio le nuove offerte di {s.name}{v}.")],
        "ess": [("o-e1", f"Volantino {s.name}{', ' + f.validity if f.validity else ''}.")],
        "giovane": [("o-g1", f"Volantino nuovo da {s.name}{v}."), ("o-g2", f"È uscito il volantino di {s.name}{v}."),
                    ("o-g3", f"Nuova settimana, nuove offerte da {s.name}{v}.")],
    }.get("voi" if f.voi else ("ess" if f.tone == "essenziale" else ("giovane" if f.tone == "giovane" else "")), [
        ("o1", f"Da oggi trovi il nuovo volantino di {s.name}{v}."), ("o2", f"È arrivato il nuovo volantino di {s.name}{v}."),
        ("o3", f"Le offerte di questa settimana da {s.name}{v}."), ("o4", f"Nuovo volantino in negozio{v}.")]), used)
    parts = [opener, "", d.hook]
    if d.detail and d.detail not in d.hook:
        parts.append(d.detail)
    rest = [o for o in f.offers if o not in d.featured]
    if rest:
        head = {"elegante": "Le altre offerte che abbiamo selezionato:", "essenziale": "Altre offerte:"}.get(
            f.tone, rng.choice(["Le altre offerte da segnare:", "In volantino anche:", "Le altre offerte della settimana:"]))
        parts += ["", head, *(_row(o) for o in rest)]
    extra = ""
    if d.kind != "combo" and f.combos:
        c = f.combos[0]
        idea = (f"Un'idea per {c.recipe.occasion}, {c.recipe.the}"
                if normalize(c.recipe.occasion.split(" ", 1)[-1]) not in normalize(c.recipe.title)
                else f"Un'idea: {c.recipe.the}")
        extra = f"{idea}: {c.names}. Con i prezzi del volantino fanno {format_eur(c.total_cents)} in tutto."
    elif d.kind != "total" and f.with_old_price >= 3 and f.total_saving >= 200:
        extra = (f"Prendendo un pezzo per ciascuna delle {f.with_old_price} offerte qui sopra con il prezzo barrato "
                 f"{'risparmiate' if f.voi else 'risparmi'} {format_eur(f.total_saving)}.")
    if extra and f.tone != "essenziale":
        parts += ["", extra]
    tail = []
    if f.where:
        tail.append(f.where + "." if f.tone == "essenziale" else ("Vi aspettiamo in " if f.voi else "Ti aspettiamo in ") + f.where + ".")
    if f.hours:
        tail.append(f"Orari: {f.hours}.")
    if tail:
        parts += ["", *tail]
    return "\n".join(parts), {"opener": opener_id}


def reel_caption(f: Facts, d: Draft, tags: list[str]) -> str:
    """Didascalia breve per Reel e TikTok: la prima riga, la validità, pochi hashtag."""
    end = f" Fino al {fmt_date(f.flyer.valid_to)}." if f.flyer.valid_to else ""
    head = d.hook if len(d.hook) <= 110 else d.hook.split(":")[0] + "."
    return f"{head}{end}\n\n" + " ".join("#" + t for t in tags[:5])


# ------------------------------------------------------------------ 5. il titolo breve (video e grafiche)

def headline(f: Facts, d: Draft) -> tuple[str, str]:
    """Titolo breve dell'idea (max ~30 caratteri) e sottotitolo, per l'apertura dei video e la grafica
    «idea della settimana». Stessa idea dei testi: la settimana ha un'unica voce."""
    k, o = d.kind, (d.featured[0] if d.featured else None)
    sub = ""
    if k == "combo":
        c = next((c for c in f.combos if list(c.items) == d.featured), f.combos[0] if f.combos else None)
        if c is not None:
            return f"{c.recipe.title}: {format_eur(c.total_cents)}", "Tutto in offerta questa settimana"
    if k == "occasion":
        start, end = week_dates(f.flyer, f.today)
        occ = next((x for x in occasions_in(start, end)), None)
        if occ is not None:
            when = _occ_when(occ).rstrip(".")
            title = f"Verso {occ.the}" if len(occ.the) <= 24 else _cap(occ.the)
            return title, when or "Le offerte della settimana"
    if k == "half" and o is not None:
        return "Metà prezzo", f"{product_name(o, False)} a {_p(o)}"
    if k == "under_euro":
        return "Sotto l'euro", f"{idea_count(f)} prodotti a meno di un euro"
    if k == "fresh":
        dept = FRESH.get(o.category, "") if o is not None else ""
        return (f"Dal reparto {dept}" if dept else "Il reparto fresco"), "Le offerte della settimana"
    if k == "stock":
        return "Settimana della scorta", "Prodotti da tenere in casa"
    if k == "weekend":
        return "Il fine settimana", "Cosa portare in tavola"
    if k == "basket":
        tot = sum(x.price_cents for x in d.featured)
        return f"Tre prodotti, {format_eur(tot)}", "Tutti in offerta questa settimana"
    if k == "total":
        return f"Risparmi {format_eur(f.total_saving)}", "Con le offerte della settimana"
    if o is not None and len(product_name(o, False)) <= 22:
        return product_name(o, False), f"a {_po(o)}"
    return "Le offerte della settimana", sub


def idea_count(f: Facts) -> int:
    return len(f.under_euro)
