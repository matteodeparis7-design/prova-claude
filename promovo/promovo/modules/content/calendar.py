"""Il calendario del commercio italiano: le ricorrenze che cambiano la spesa.

Si usano solo fatti veri (la data della ricorrenza) e i prodotti che sono davvero nel volantino:
la redazione non promette nulla sui prodotti, li collega al momento dell'anno.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


def easter(year: int) -> date:
    """Domenica di Pasqua (calendario gregoriano, algoritmo di Meeus/Jones/Butcher)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    month = (h + l_ - 7 * m + 114) // 31
    day = ((h + l_ - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def _nth_sunday(year: int, month: int, n: int) -> date:
    d = date(year, month, 1)
    d += timedelta(days=(6 - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


@dataclass(frozen=True)
class Occasion:
    key: str
    name: str                 # "Pasqua"
    day: date                 # il giorno della ricorrenza
    lead: int                 # quanti giorni prima comincia a "contare" nella spesa
    words: tuple[str, ...]    # prodotti tipici (parole chiave, minuscole e senza accenti)
    article: str = ""         # "la", "il", "l'", "" (per le frasi: "verso la Festa della mamma")

    @property
    def the(self) -> str:
        return f"{self.article}{' ' if self.article and not self.article.endswith(chr(39)) else ''}{self.name}".strip()


def occasions_of(year: int) -> list[Occasion]:
    e = easter(year)
    return [
        Occasion("epifania", "Befana", date(year, 1, 6), 5, ("calza", "caramell", "cioccolat", "torrone"), "la"),
        Occasion("carnevale", "Carnevale", e - timedelta(days=47), 10,
                 ("frappe", "chiacchiere", "castagnole", "zucchero a velo", "olio di semi"), "il"),
        Occasion("sanvalentino", "San Valentino", date(year, 2, 14), 5,
                 ("cioccolat", "spumante", "prosecco", "fragol", "vino", "rose", "fiori")),
        Occasion("donna", "Festa della donna", date(year, 3, 8), 3, ("mimosa", "fiori", "torta", "cioccolat"), "la"),
        Occasion("papa", "Festa del papà", date(year, 3, 19), 5, ("zeppole", "vino", "birra", "cioccolat"), "la"),
        Occasion("pasqua", "Pasqua", e, 12,
                 ("colomba", "uovo di", "uova di cioccolat", "agnello", "carciof", "asparag", "casatiello", "pastiera",
                  "ricotta", "spumante", "salame", "corallina"), ""),
        Occasion("pasquetta", "Pasquetta", e + timedelta(days=1), 4,
                 ("salsicc", "carbone", "birra", "pane", "salame", "formagg", "piatti", "bicchieri"), ""),
        Occasion("mamma", "Festa della mamma", _nth_sunday(year, 5, 2), 6, ("fiori", "pianta", "torta", "cioccolat"), "la"),
        Occasion("estate", "inizio dell'estate", date(year, 6, 21), 7,
                 ("anguria", "melone", "gelato", "acqua", "birra", "pesche", "insalat", "crema solare"), "l'"),
        Occasion("ferragosto", "Ferragosto", date(year, 8, 15), 8,
                 ("anguria", "melone", "gelato", "birra", "acqua", "salsicc", "costin", "carbone", "ghiaccio"), ""),
        Occasion("scuola", "rientro a scuola", date(year, 9, 14), 14,
                 ("merendin", "succo", "succhi", "biscott", "cereali", "latte", "crackers", "quaderni", "zaino"), "il"),
        Occasion("halloween", "Halloween", date(year, 10, 31), 7, ("zucca", "caramell", "cioccolat", "dolcett"), ""),
        Occasion("morti", "Ognissanti", date(year, 11, 1), 4, ("fiori", "crisantem", "fave dei morti", "ossa dei morti"), ""),
        Occasion("immacolata", "Immacolata", date(year, 12, 8), 4, ("albero", "addobbi", "panettone", "pandoro"), "l'"),
        Occasion("natale", "Natale", date(year, 12, 25), 18,
                 ("panettone", "pandoro", "torrone", "spumante", "prosecco", "cotechino", "zampone", "lenticch",
                  "salmone", "frutta secca", "noci", "datteri", "capitone", "baccala", "tortellini", "panforte"), ""),
        Occasion("capodanno", "Capodanno", date(year, 12, 31), 5,
                 ("cotechino", "zampone", "lenticch", "spumante", "prosecco", "uva"), ""),
    ]


def occasions_in(start: date, end: date) -> list[Occasion]:
    """Le ricorrenze che cadono nei giorni del volantino o subito dopo (la spesa si fa prima)."""
    out = []
    for year in {start.year, end.year}:
        for o in occasions_of(year):
            if start <= o.day + timedelta(days=0) and o.day - timedelta(days=o.lead) <= end:
                out.append(o)
    out.sort(key=lambda o: o.day)
    return out
