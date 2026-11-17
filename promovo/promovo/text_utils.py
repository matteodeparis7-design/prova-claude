"""Utilità sui testi: categorie merceologiche, date di validità, confronto di nomi."""
from __future__ import annotations

import re
import unicodedata
from datetime import date
from difflib import SequenceMatcher

CATEGORIES = [
    "frutta e verdura", "carne", "pesce", "salumi e formaggi", "latte e latticini", "uova",
    "pane e forno", "pasta e riso", "dispensa", "surgelati", "dolci e snack", "colazione",
    "bevande", "vino e alcolici", "igiene casa", "cura persona", "infanzia", "animali", "altro",
]

_KEYWORDS: dict[str, tuple[str, ...]] = {
    "frutta e verdura": ("mela", "mele", "banan", "arance", "arancia", "pera", "pere", "uva", "kiwi", "limon",
                         "insalata", "pomodor", "patate", "zucchin", "carot", "cipoll", "verdur", "frutta",
                         "fragol", "melanzan", "peperon", "finocch", "agrum", "mandarin", "clementin"),
    "carne": ("pollo", "manzo", "bovino", "suino", "maiale", "vitello", "tacchino", "salsicc", "hamburger",
              "bistecc", "macinato", "fesa", "petto di", "costat", "agnello", "carne", "arrosto", "spiedini"),
    "pesce": ("salmone", "tonno fresco", "merluzzo", "orata", "branzino", "gamber", "cozze", "vongole",
              "calamar", "polpo", "pesce", "seppi", "alici", "baccal", "spigola", "platessa", "nasello"),
    "salumi e formaggi": ("prosciutto", "salame", "mortadella", "bresaola", "speck", "pancetta", "parmigiano",
                          "grana", "pecorino", "mozzarella", "formagg", "gorgonzola", "provolone", "stracchino",
                          "ricotta", "wurstel", "würstel", "scamorza", "fontina", "asiago", "emmental"),
    "latte e latticini": ("latte", "yogurt", "burro", "panna", "kefir", "mascarpone", "skyr"),
    "uova": ("uova", "uovo"),
    "pane e forno": ("pane", "panino", "focaccia", "grissini", "fette biscottate", "crackers", "cracker",
                     "pizza fresca", "piadina", "tramezzin"),
    "pasta e riso": ("pasta", "spaghetti", "penne", "fusilli", "rigatoni", "riso", "gnocchi", "lasagn",
                     "tortellini", "ravioli", "farfalle", "linguine", "tagliatelle", "orecchiette"),
    "dispensa": ("passata", "olio", "aceto", "passata", "pelati", "sugo", "pesto", "tonno", "legumi", "fagioli", "ceci",
                 "lenticchie", "farina", "zucchero", "sale", "maionese", "ketchup", "brodo", "dado", "conserv",
                 "mais", "piselli", "spezie", "olive", "sottoli"),
    "surgelati": ("surgelat", "gelat", "bastoncini", "sofficini", "findus", "frozen", "pizza surgelata",
                  "verdure grigliate surg", "minestrone surg", "patatine fritte"),
    "dolci e snack": ("cioccolat", "biscott", "merendin", "patatine", "snack", "caramell", "torta", "crostat",
                      "wafer", "nutella", "pandoro", "panettone", "colomba", "praline", "barrett"),
    "colazione": ("caffè", "caffe", "cereali", "muesli", "tè ", "the ", "tisana", "marmellata", "confettura",
                  "miele", "cappuccino", "orzo solubile", "capsule"),
    "bevande": ("acqua", "bibita", "cola", "aranciata", "succo", "tè freddo", "the freddo", "energy drink",
                "gassata", "frizzante", "naturale", "sprite", "fanta", "chinotto"),
    "vino e alcolici": ("vino", "birra", "prosecco", "spumante", "amaro", "grappa", "whisky", "vodka", "gin",
                        "rum", "liquore", "chianti", "lambrusco", "montepulciano", "aperitivo"),
    "igiene casa": ("detersiv", "ammorbident", "candeggin", "sgrassator", "pavimenti", "piatti", "lavastovigli",
                    "carta igienica", "rotoloni", "scottex", "tovaglioli", "spugn", "sacchetti", "detergente",
                    "bucato", "pastiglie"),
    "cura persona": ("shampoo", "balsamo", "bagnoschiuma", "dentifricio", "spazzolino", "deodorante",
                     "sapone", "crema", "rasoi", "assorbent", "cotton", "struccant", "docciaschiuma"),
    "infanzia": ("pannolin", "omogeneizzat", "baby", "neonat", "salviettine"),
    "animali": ("cane", "cani", "gatto", "gatti", "crocchette", "pet", "lettiera", "umido per"),
}


def normalize(text: str) -> str:
    """Minuscolo, senza accenti e senza punteggiatura: per i confronti."""
    t = unicodedata.normalize("NFKD", text or "")
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def categorize(name: str, description: str = "") -> str:
    hay = " " + (name + " " + description).lower() + " "
    # Nei nomi italiani il prodotto viene prima ("Caffè macinato", "Passata di pomodoro"):
    # vince la parola chiave che compare per prima; a parità, la più lunga.
    best, best_key = "altro", None
    for cat, words in _KEYWORDS.items():
        for w in words:
            # La parola chiave deve iniziare una parola: "gin" non trova "originale".
            m = re.search(r"(?<![a-zà-ÿ])" + re.escape(w.strip()), hay)
            if m:
                key = (m.start(), -len(w))
                if best_key is None or key < best_key:
                    best, best_key = cat, key
    return best


def coerce_category(value: str | None, name: str = "", description: str = "") -> str:
    v = (value or "").strip().lower()
    if v in CATEGORIES and v != "altro":
        return v
    return categorize(name, description)


def similarity(a: str, b: str) -> float:
    na, nb = normalize(a), normalize(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    ratio = SequenceMatcher(None, na, nb).ratio()
    ta, tb = set(na.split()), set(nb.split())
    jacc = len(ta & tb) / len(ta | tb) if ta | tb else 0.0
    contained = 0.9 if (na in nb or nb in na) and min(len(na), len(nb)) >= 4 else 0.0
    return max(ratio, jacc, contained)


_MONTHS = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6, "luglio": 7,
    "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12,
    "gen": 1, "feb": 2, "mar": 3, "apr": 4, "mag": 5, "giu": 6, "lug": 7, "ago": 8, "set": 9, "ott": 10,
    "nov": 11, "dic": 12,
}
_MONTH_RE = "|".join(sorted(_MONTHS, key=len, reverse=True))


def _safe_date(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def parse_validity(text: str, today: date | None = None) -> tuple[date | None, date | None]:
    """Trova il periodo di validità in frasi come:
    'dal 13 al 22 ottobre', 'dal 28 ottobre al 6 novembre 2026', 'dal 13/10 al 22/10/2026'.
    """
    today = today or date.today()
    t = re.sub(r"\s+", " ", (text or "").lower())
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))

    m = re.search(
        rf"dal\s+(\d{{1,2}})(?:\s+({_MONTH_RE})\w*)?(?:\s+(\d{{4}}))?\s+al\s+(\d{{1,2}})\s+({_MONTH_RE})\w*(?:\s+(\d{{4}}))?",
        t)
    if m:
        d1, mo1, y1, d2, mo2, y2 = m.groups()
        m2 = _MONTHS[mo2]
        m1 = _MONTHS[mo1] if mo1 else m2
        return _resolve_years(today, int(d1), m1, int(y1) if y1 else None, int(d2), m2, int(y2) if y2 else None)

    m = re.search(r"dal\s+(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2,4}))?\s+al\s+(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2,4}))?", t)
    if m:
        d1, m1, y1, d2, m2, y2 = m.groups()

        def year(y: str | None) -> int | None:
            if not y:
                return None
            return int(y) + 2000 if len(y) == 2 else int(y)
        return _resolve_years(today, int(d1), int(m1), year(y1), int(d2), int(m2), year(y2))
    return None, None


def _resolve_years(today: date, d1: int, m1: int, y1: int | None, d2: int, m2: int,
                   y2: int | None) -> tuple[date | None, date | None]:
    """Completa gli anni mancanti scegliendo il periodo più vicino a oggi."""
    # Il periodo attraversa il capodanno solo se il mese di inizio viene dopo quello di fine.
    crosses = m1 > m2
    if y2 is None and y1 is not None:
        y2 = y1 + 1 if crosses else y1
    if y2 is not None:
        if y1 is None:
            y1 = y2 - 1 if crosses else y2
        start, end = _safe_date(y1, m1, d1), _safe_date(y2, m2, d2)
        if start is None or end is None or start > end:
            return None, None
        return start, end
    best: tuple[date | None, date | None] = (None, None)
    best_gap = None
    for cand in (today.year - 1, today.year, today.year + 1):
        start = _safe_date(cand - 1 if crosses else cand, m1, d1)
        end = _safe_date(cand, m2, d2)
        if start is None or end is None or start > end:
            continue
        gap = 0 if start <= today <= end else min(abs((start - today).days), abs((end - today).days))
        if best_gap is None or gap < best_gap:
            best, best_gap = (start, end), gap
    return best


def parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError:
        return None
