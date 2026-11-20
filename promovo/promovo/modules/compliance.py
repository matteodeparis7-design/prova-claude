"""Le regole di legge sui contenuti promozionali, in un posto solo.

Due controlli, usati da tutti gli agenti:

1. **Prodotti che non si possono pubblicizzare.** Escono da grafiche, video, testi, radio, cartellini promozionali
   e locandine; il Correttore li segnala se sono nella bozza del volantino.
   - tabacco e sigarette elettroniche: pubblicità vietata (L. 165/1962; D.Lgs. 6/2016, art. 21);
   - giochi con vincite in denaro (gratta e vinci, lotto, scommesse): pubblicità vietata («Decreto Dignità»,
     D.L. 87/2018, art. 9);
   - latte per lattanti (formule di partenza 0-6 mesi): pubblicità e promozioni vietate nei punti vendita
     (D.M. 82/2009, attuazione della Direttiva 2006/141/CE; Reg. UE 2016/127);
   - farmaci: la pubblicità al pubblico richiede l'autorizzazione del Ministero della Salute (D.Lgs. 219/2006,
     artt. 115-118); Promovo non la prepara.

2. **Frasi da non scrivere.** Il Revisore e il caporedattore scartano i testi che le contengono:
   - concorsi, estrazioni, «vinci»: sono manifestazioni a premio con procedure e cauzioni (DPR 430/2001);
   - superlativi non dimostrabili e confronti con altri negozi («i prezzi più bassi», «imbattibili»): pratiche
     ingannevoli e pubblicità comparativa (Codice del Consumo, artt. 20-22; D.Lgs. 145/2007);
   - proprietà salutari dei cibi («fa bene», «rinforza le difese», «dimagrante»): solo le indicazioni autorizzate
     dal Reg. CE 1924/2006 e dal Reg. UE 432/2012, che Promovo non scrive;
   - «km zero», «biologico» e simili detti da Promovo: dichiarazioni da provare (Reg. UE 2018/848 per il bio);
   - alcol associato a minori, guida, sport, salute o prestazioni (L. 125/2001, art. 13).
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Restriction:
    code: str
    label: str
    law: str


TOBACCO = Restriction("tabacco", "tabacco e sigarette elettroniche",
                      "pubblicità vietata (L. 165/1962; D.Lgs. 6/2016, art. 21)")
GAMBLING = Restriction("gioco", "giochi con vincite in denaro",
                       "pubblicità vietata (D.L. 87/2018 «Decreto Dignità», art. 9)")
INFANT = Restriction("lattanti", "latte per lattanti (0-6 mesi)",
                     "pubblicità e promozioni vietate nei punti vendita (D.M. 82/2009; Reg. UE 2016/127)")
MEDICINE = Restriction("farmaci", "farmaci",
                       "la pubblicità al pubblico richiede l'autorizzazione del Ministero della Salute "
                       "(D.Lgs. 219/2006, artt. 115-118)")

_TOBACCO = re.compile(r"\b(sigarett\w*|sigar[oi]|tabacc\w*|trinciato|iqos|heets|terea|e-?cig\w*|svapo|nicotin\w*|"
                      r"cartine per sigarett\w*)\b", re.I)
_GAMBLING = re.compile(r"\b(gratta e vinci|(super)?enalotto|10 ?e ?lotto|lotteri\w*|scommess\w*|slot machine)\b", re.I)
_INFANT_WORDS = re.compile(r"\b(per lattanti|di partenza|formula per lattanti|0 ?- ?6 mesi|dalla nascita)\b", re.I)
_INFANT_BRANDS = re.compile(r"\b(mellin|aptamil|humana|nidina|blemil|hipp|milupa|nutricia|plasmon|neolatte|"
                            r"novalac|similac|enfamil|nan optipro)\b", re.I)
_MEDICINE = re.compile(r"\b(farmac[oi]|medicinal[ei]|paracetamolo|ibuprofene|acido acetilsalicilico|tachipirina|"
                       r"aspirina|brufen|moment act|bentelan|antidolorific\w*|antinfiammatori\w*|"
                       r"sciroppo per la tosse)\b", re.I)


def restriction(name: str, description: str = "", brand: str = "", category: str = "") -> Restriction | None:
    """Il divieto che riguarda il prodotto, oppure None se si può pubblicizzare."""
    text = " ".join(x for x in (brand, name, description) if x)
    if _TOBACCO.search(text):
        return TOBACCO
    if _GAMBLING.search(text):
        return GAMBLING
    low = text.lower()
    if "latte" in low and (_INFANT_WORDS.search(text)
                           or (_INFANT_BRANDS.search(text) and re.search(r"\b1\b", text)
                               and not re.search(r"\b1\s*(l|lt|litro|kg)\b", low))):
        return INFANT
    if _MEDICINE.search(text):
        return MEDICINE
    return None


def offer_restriction(o) -> Restriction | None:
    return restriction(getattr(o, "name", "") or "", getattr(o, "description", "") or "",
                       getattr(o, "brand", "") or "", getattr(o, "category", "") or "")


def advertisable(offers) -> list:
    """Le offerte che si possono usare nei contenuti promozionali."""
    return [o for o in offers if offer_restriction(o) is None]


# ----------------------------------------------------------------- frasi

_ALCOHOL = re.compile(r"\b(vin[oi]|birr[ae]|spumant\w*|prosecc\w*|liquor\w*|amar[oi]|grappa|whisky|vodka|gin|rum|"
                      r"aperitiv\w*|alcol\w*|cocktail)\b", re.I)
_ALCOHOL_BAD = re.compile(r"\b(bambin\w*|ragazz\w*|scuola|merenda|guida\w*|al volante|sport\w*|energia|"
                          r"salute|fa bene|prestazion\w*|carica)\b", re.I)

PHRASES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(concors[oi]|in palio|estrazion\w*|sorteggi\w*|vinci|vincere|vincerai|vincitor\w*|giveaway|"
                r"lotteri\w*)\b", re.I),
     "concorsi ed estrazioni sono manifestazioni a premio con procedure e cauzioni (DPR 430/2001)"),
    (re.compile(r"\b(prezzi più bassi|il più convenient\w*|i più convenienti|il più economic\w*|i prezzi migliori|"
                r"miglior prezzo|imbattibil\w*|nessuno costa meno|più convenienti di|meno car[oi] di tutti)\b", re.I),
     "superlativo che non si può dimostrare (Codice del Consumo, artt. 20-22)"),
    (re.compile(r"\b(della concorrenza|dei concorrenti|degli altri supermercat\w*|rispetto agli altri negoz\w*)\b",
                re.I),
     "confronto con altri negozi: la pubblicità comparativa ha regole precise (D.Lgs. 145/2007)"),
    (re.compile(r"\b(fa bene|salutar[ei]|rinforza\w*|difese immunitarie|dimagr\w*|brucia ?grassi|detox|depurativ\w*|"
                r"previene|curativ\w*|terapeutic\w*|abbassa il colesterolo)\b", re.I),
     "proprietà salutari: ammesse solo le indicazioni autorizzate (Reg. CE 1924/2006)"),
    (re.compile(r"\b(km ?0|km zero|chilometro zero|a chilometri zero)\b", re.I),
     "«km zero» è una dichiarazione da provare (in alcune regioni ha un significato di legge)"),
    (re.compile(r"\b(sigarett\w*|tabacc\w*|gratta e vinci|scommess\w*|slot machine)\b", re.I),
     "tabacco e giochi con vincite in denaro non si possono pubblicizzare"),
]


def text_issues(text: str) -> list[str]:
    """Le frasi del testo che la legge non permette, con il motivo."""
    out = []
    for rx, why in PHRASES:
        m = rx.search(text or "")
        if m:
            out.append(f"«{m.group(0)}»: {why}")
    if _ALCOHOL.search(text or "") and _ALCOHOL_BAD.search(text or ""):
        m = _ALCOHOL_BAD.search(text)
        out.append(f"«{m.group(0)}» vicino a una bevanda alcolica: non si associa l'alcol a minori, guida, sport, "
                   "salute o prestazioni (L. 125/2001, art. 13)")
    return out


# ----------------------------------------------------------------- premi della «Parola alla cassa»

_GIFT = re.compile(r"\b(omagg\w*|regal\w*|gratis|gratuit\w*|in premio|premio|estrazion\w*|buono acquisto|"
                   r"punti doppi|vinci|in palio|campion\w*)\b", re.I)
_DISCOUNT = re.compile(r"(\d+\s*%|\bsconto\b|€\s*\d|\d+\s*euro\b)", re.I)


def reward_issue(text: str) -> str | None:
    """Il premio della parola alla cassa deve essere uno sconto: gli sconti non sono «operazioni a premio»
    (DPR 430/2001, art. 6). Omaggi, regali, buoni e punti richiedono regolamento e cauzione."""
    if _GIFT.search(text or "") or not _DISCOUNT.search(text or ""):
        return ("Scrivi uno sconto (per esempio «il 5% di sconto sulla spesa»): omaggi, regali, buoni e punti "
                "sono «operazioni a premio» e richiedono regolamento e cauzione (DPR 430/2001).")
    return None
