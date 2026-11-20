"""Banco e allergeni: cartelli e registro per i prodotti venduti sfusi (gastronomia, forno, pescheria...).

Per gli alimenti non preimballati l'informazione sui 14 allergeni (Allegato II del Reg. UE 1169/2011) è obbligatoria
e in Italia la regola il D.Lgs. 231/2017 (art. 19): va data per iscritto, riconducibile a ciascun prodotto, con un
cartello, un registro o un sistema equivalente ben in vista.

Promovo legge gli ingredienti scritti dal negozio, **propone** gli allergeni e segnala i casi dubbi («farina» senza
specificare, brodo e dado, spezie, vino...). Gli allergeni li **conferma sempre una persona**, il cui nome e la data
finiscono nel registro: la responsabilità resta dell'operatore alimentare, Promovo aiuta a non dimenticare niente.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw

from ..models import CounterItem, Store
from .video.render import INK, WHITE, fit_text, font, hex_rgb, mix, readable_on_paper

COUNTERS = {"gastronomia": "Gastronomia", "forno": "Forno e pasticceria", "salumeria": "Salumi e formaggi",
            "pescheria": "Pescheria", "macelleria": "Macelleria", "pronti": "Piatti pronti", "altro": "Altro"}

# (codice, nome, parole che lo indicano, parole che lo fanno sospettare)
ALLERGENS: list[tuple[str, str, list[str], list[str]]] = [
    ("glutine", "Cereali con glutine", ["grano", "frumento", "segale", "orzo", "avena", "farro", "kamut", "spelta",
     "semola", "semolino", "pangrattato", "pan grattato", "pane", "pasta", "couscous", "cous cous", "bulgur",
     "seitan", "glutine", "malto", "farina 0", "farina 00", "farina di grano", "farina di frumento", "crostini",
     "grissini", "taralli", "pasta sfoglia", "pasta frolla", "pan di spagna", "biscotti", "besciamella"],
     ["farina", "amido", "addensante", "panatura", "impanato", "impanata"]),
    ("crostacei", "Crostacei", ["gamberi", "gambero", "gamberetti", "scampi", "scampo", "mazzancolle", "aragosta",
     "astice", "granchio", "granceola", "canocchie", "cicale di mare"], ["surimi", "frutti di mare"]),
    ("uova", "Uova", ["uovo", "uova", "albume", "tuorlo", "maionese", "frittata", "pasta all'uovo", "lisozima"],
     ["pasta fresca", "panatura"]),
    ("pesce", "Pesce", ["pesce", "tonno", "salmone", "merluzzo", "baccala", "stoccafisso", "acciughe", "acciuga",
     "alici", "sardine", "sarde", "orata", "spigola", "branzino", "pesce spada", "sgombro", "trota", "nasello",
     "platessa", "surimi", "colatura", "bottarga", "colla di pesce"], ["salsa worcester"]),
    ("arachidi", "Arachidi", ["arachidi", "arachide", "noccioline", "burro di arachidi", "olio di arachide"],
     ["olio di semi"]),
    ("soia", "Soia", ["soia", "soya", "tofu", "edamame", "salsa di soia", "lecitina di soia", "tempeh", "miso"],
     ["lecitina", "proteine vegetali"]),
    ("latte", "Latte e lattosio", ["latte", "burro", "panna", "formaggio", "formaggi", "mozzarella", "parmigiano",
     "grana", "pecorino", "ricotta", "mascarpone", "stracchino", "provola", "scamorza", "fontina", "gorgonzola",
     "yogurt", "lattosio", "caseina", "caseinato", "siero di latte", "besciamella", "burrata", "caciocavallo",
     "taleggio", "emmental", "crescenza", "squacquerone", "provolone", "asiago"], ["panna vegetale"]),
    ("frutta_guscio", "Frutta a guscio", ["mandorle", "mandorla", "nocciole", "nocciola", "noci", "noce", "anacardi",
     "pistacchi", "pistacchio", "noci pecan", "noci del brasile", "noci di macadamia", "macadamia",
     "granella di nocciole", "pasta di mandorle", "amaretti", "torrone", "gianduia", "marzapane"],
     ["pesto", "frutta secca"]),
    ("sedano", "Sedano", ["sedano", "sedano rapa"], ["brodo", "dado", "soffritto", "verdure miste", "minestrone",
     "spezie", "aromi"]),
    ("senape", "Senape", ["senape", "mostarda"], ["salse", "maionese", "spezie", "condimento"]),
    ("sesamo", "Semi di sesamo", ["sesamo", "tahina", "tahini", "gomasio"], ["semi misti"]),
    ("solfiti", "Anidride solforosa e solfiti", ["solfiti", "anidride solforosa", "metabisolfito", "e220", "e221",
     "e222", "e223", "e224", "e226", "e227", "e228"], ["vino", "aceto", "aceto di vino", "aceto balsamico",
     "frutta secca", "uvetta", "funghi secchi", "marsala"]),
    ("lupini", "Lupini", ["lupini", "lupino", "farina di lupini"], []),
    ("molluschi", "Molluschi", ["cozze", "vongole", "calamari", "calamaro", "totani", "polpo", "polpi", "seppie",
     "seppia", "ostriche", "capesante", "lumache", "moscardini", "fasolari", "cannolicchi"], ["frutti di mare"]),
]
CODES = [a[0] for a in ALLERGENS]
LABEL = {a[0]: a[1] for a in ALLERGENS}
SHORT = {"glutine": "Glutine", "crostacei": "Crostacei", "uova": "Uova", "pesce": "Pesce", "arachidi": "Arachidi",
         "soia": "Soia", "latte": "Latte", "frutta_guscio": "Frutta a guscio", "sedano": "Sedano", "senape": "Senape",
         "sesamo": "Sesamo", "solfiti": "Solfiti", "lupini": "Lupini", "molluschi": "Molluschi"}
WHY = {"farina": "«farina» senza dire di cosa: se è di grano contiene glutine",
       "amido": "amido: se è di frumento contiene glutine",
       "brodo": "brodo: spesso contiene sedano", "dado": "dado: spesso contiene sedano",
       "soffritto": "soffritto: di solito contiene sedano", "spezie": "spezie: possono contenere sedano o senape",
       "vino": "vino: contiene solfiti (sopra 10 mg/kg vanno dichiarati)",
       "aceto": "aceto: di solito contiene solfiti", "pesto": "pesto: spesso contiene anacardi o altra frutta a guscio",
       "olio di semi": "olio di semi: verifica che non sia di arachide",
       "lecitina": "lecitina: verifica che non sia di soia", "surimi": "surimi: può contenere crostacei",
       "frutta secca": "frutta secca: se sono noci, mandorle o nocciole è frutta a guscio"}


class AllergenError(ValueError):
    pass


def _norm(s: str) -> str:
    s = "".join(c for c in unicodedata.normalize("NFD", (s or "").lower()) if unicodedata.category(c) != "Mn")
    s = s.replace("’", "'")
    return " " + re.sub(r"[^a-z0-9']+", " ", s) + " "


# parole che sembrano allergeni ma non lo sono per la legge (o lo sono di un altro tipo)
NOT_ALLERGEN = {"noce moscata": "spezia", "noci di cocco": "cocco", "noce di cocco": "cocco", "burro di cacao": "cacao",
                "latte di cocco": "cocco", "latte di riso": "riso", "latte di avena": "avena", "latte di soia": "soia",
                "latte di mandorla": "mandorla", "pasta di olive": "olive", "fiocchi di patate": "patate"}


def _rewrite(t: str) -> str:
    for k, v in NOT_ALLERGEN.items():
        t = t.replace(f" {_norm(k).strip()} ", f" {v} ")
    return t


def _strip_without(t: str) -> str:
    """Toglie «senza X» (es. «senza glutine»): non è un ingrediente."""
    return re.sub(r" senza [a-z']+( [a-z']+)?", " ", t)


def detect(ingredients: str) -> dict:
    """Allergeni proposti (con le parole trovate) e dubbi da verificare."""
    t = _rewrite(_strip_without(_norm(ingredients)))
    found: dict[str, list[str]] = {}
    doubts: list[dict] = []
    for code, _label, words, maybe in ALLERGENS:
        hits = [w for w in words if f" {_norm(w).strip()} " in t]
        if hits:
            found[code] = hits
    for code, _label, _words, maybe in ALLERGENS:
        if code in found:
            continue
        for w in maybe:
            if f" {_norm(w).strip()} " in t:
                doubts.append({"code": code, "word": w, "why": WHY.get(w, f"«{w}»: verifica se contiene {LABEL[code].lower()}")})
                break
    return {"allergens": [c for c in CODES if c in found], "matches": found, "doubts": doubts}


def clean(data: dict) -> dict:
    name = " ".join(str(data.get("name") or "").split())
    ingredients = " ".join(str(data.get("ingredients") or "").split())
    counter = str(data.get("counter") or "gastronomia")
    checked_by = " ".join(str(data.get("checked_by") or "").split())
    if len(name) < 2:
        raise AllergenError("Scrivi il nome del prodotto.")
    if len(name) > 160:
        raise AllergenError("Il nome è troppo lungo.")
    if counter not in COUNTERS:
        raise AllergenError("Banco non valido.")
    if len(ingredients) < 3:
        raise AllergenError("Scrivi gli ingredienti: servono per gli allergeni.")
    if len(ingredients) > 2000:
        raise AllergenError("Elenco degli ingredienti troppo lungo.")
    if len(checked_by) < 2:
        raise AllergenError("Scrivi chi ha controllato gli allergeni: il registro deve dirlo.")
    allergens = [c for c in CODES if c in set(data.get("allergens") or [])]
    may = [c for c in CODES if c in set(data.get("may_contain") or []) and c not in allergens]
    return {"name": name, "ingredients": ingredients, "counter": counter, "checked_by": checked_by[:80],
            "allergens": allergens, "may_contain": may}


def apply(item: CounterItem, data: dict) -> CounterItem:
    for k, v in clean(data).items():
        setattr(item, k, v)
    item.checked_at = datetime.now(timezone.utc)
    return item


def missing(item: CounterItem) -> list[str]:
    """Allergeni che gli ingredienti fanno pensare ma che la persona non ha segnato (da ricontrollare)."""
    return [c for c in detect(item.ingredients)["allergens"] if c not in (item.allergens or [])]


# ----------------------------------------------------------------- testo con gli allergeni in evidenza

def _bold_words(item: CounterItem) -> set[str]:
    out = set()
    for code, _l, words, maybe in ALLERGENS:
        if code in (item.allergens or []):
            out |= {_norm(w).strip() for w in words + maybe}
    return out


def _rich_lines(text: str, bold: set[str], width: int, size: int) -> list[list[tuple[str, bool]]]:
    """Va a capo parola per parola; le parole degli allergeni in grassetto (anche se fanno parte di più parole)."""
    tokens = text.split()
    norm = [_norm(t).strip() for t in tokens]
    flags = [False] * len(tokens)
    for i in range(len(tokens)):
        for n in (3, 2, 1):
            if i + n <= len(tokens) and " ".join(norm[i:i + n]) in bold:
                for j in range(i, i + n):
                    flags[j] = True
                break
    lines, cur, cur_w = [], [], 0.0
    reg, bold_f = font(size), font(size, True)
    space = reg.getlength(" ")
    for tok, b in zip(tokens, flags):
        w = (bold_f if b else reg).getlength(tok.upper() if b else tok)
        if cur and cur_w + space + w > width:
            lines.append(cur)
            cur, cur_w = [], 0.0
        cur.append((tok.upper() if b else tok, b))
        cur_w += (space if len(cur) > 1 else 0) + w
    if cur:
        lines.append(cur)
    return lines


def _draw_rich(d: ImageDraw.ImageDraw, x: int, y: int, lines, size: int, color, max_lines: int) -> int:
    reg, bold_f = font(size), font(size, True)
    space = reg.getlength(" ")
    lh = int(size * 1.3)
    for line in lines[:max_lines]:
        cx = x
        for tok, b in line:
            f = bold_f if b else reg
            d.text((cx, y), tok, font=f, fill=color)
            cx += f.getlength(tok) + space
        y += lh
    return y


# ----------------------------------------------------------------- cartellini, registro, cartello

def label_image(store: Store, item: CounterItem) -> Image.Image:
    """Cartellino per il banco (105 x 74 mm): nome, ingredienti con gli allergeni in evidenza, allergeni."""
    w, h = 1240, 877
    brand = hex_rgb(store.brand_color)
    img = Image.new("RGB", (w, h), WHITE)
    d = ImageDraw.Draw(img)
    pad = 46
    d.rectangle((0, 0, w, 96), fill=brand)
    fg = WHITE if sum(brand) < 600 else INK
    d.text((pad, 48), COUNTERS.get(item.counter, "Banco").upper(), font=font(40, True), fill=fg, anchor="lm")
    d.text((w - pad, 48), store.name[:34], font=font(32), fill=fg, anchor="rm")
    fn, ln = fit_text(item.name, w - 2 * pad, 150, 66, True, 2, min_size=40)
    y = 120
    for line in ln:
        d.text((pad, y), line, font=fn, fill=INK)
        y += int(fn.size * 1.15)
    y += 10
    foot = 150
    room = h - foot - y - 20
    bold = _bold_words(item)
    for size in (54, 48, 44, 40, 36, 32, 28, 25, 22):           # il testo più grande che entra nello spazio
        lines = _rich_lines("Ingredienti: " + item.ingredients, bold, w - 2 * pad, size)
        if len(lines) * int(size * 1.3) <= room:
            break
    n = min(len(lines), max(1, room // int(size * 1.3)))
    y += max(0, (room - n * int(size * 1.3)) // 2)            # blocco centrato nello spazio libero
    _draw_rich(d, pad, y, lines, size, (40, 44, 56), n)
    d.rectangle((0, h - foot, w, h), fill=mix(brand, WHITE, 0.9))
    al = ", ".join(SHORT[c] for c in item.allergens) or "nessuno dei 14 allergeni"
    fa, la = fit_text(f"Allergeni: {al}", w - 2 * pad, 60, 40, True, 1)
    d.text((pad, h - foot + 42), la[0], font=fa, fill=readable_on_paper(brand), anchor="lm")
    if item.may_contain:
        mc = ", ".join(SHORT[c] for c in item.may_contain)
        fm_, lm = fit_text(f"Può contenere tracce di: {mc}", w - 2 * pad, 50, 30, False, 1)
        d.text((pad, h - foot + 100), lm[0], font=fm_, fill=INK, anchor="lm")
    else:
        d.text((pad, h - foot + 100), "Per informazioni chiedi al personale del banco.", font=font(28), fill=INK,
               anchor="lm")
    return img


def labels_pdf(store: Store, items: list[CounterItem], out: Path) -> Path:
    if not items:
        raise AllergenError("Nessun prodotto del banco.")
    W, H = 2480, 3508
    tw, th = W // 2, H // 4
    pages = []
    for start in range(0, len(items), 8):
        page = Image.new("RGB", (W, H), WHITE)
        for k, it in enumerate(items[start:start + 8]):
            lab = label_image(store, it)
            lab.thumbnail((tw - 36, th - 36), Image.LANCZOS)
            page.paste(lab, ((k % 2) * tw + (tw - lab.width) // 2, (k // 2) * th + (th - lab.height) // 2))
        dd = ImageDraw.Draw(page)
        for x in range(0, W, 28):
            for r in range(1, 4):
                dd.line((x, r * th, x + 14, r * th), fill=(170, 170, 170), width=2)
        for y in range(0, H, 28):
            dd.line((tw, y, tw, y + 14), fill=(170, 170, 170), width=2)
        pages.append(page)
    out.parent.mkdir(parents=True, exist_ok=True)
    pages[0].save(out, "PDF", resolution=300, save_all=True, append_images=pages[1:])
    return out


def register_pdf(store: Store, items: list[CounterItem], out: Path) -> Path:
    """Il registro degli allergeni: una riga per prodotto, una colonna per allergene, chi ha controllato e quando."""
    if not items:
        raise AllergenError("Nessun prodotto del banco.")
    W, H = 3508, 2480                                    # A4 orizzontale, 300 dpi
    brand = hex_rgb(store.brand_color)
    name_w = 900
    col_w = (W - 2 * 120 - name_w - 420) // 14
    rows_per_page = 18
    pages = []
    groups = sorted(items, key=lambda i: (list(COUNTERS).index(i.counter) if i.counter in COUNTERS else 99, i.name))
    for start in range(0, len(groups), rows_per_page):
        img = Image.new("RGB", (W, H), WHITE)
        d = ImageDraw.Draw(img)
        x0 = 120
        d.text((x0, 110), "Registro degli allergeni", font=font(90, "display"), fill=INK, anchor="lm")
        d.text((W - 120, 110), store.name, font=font(52, True), fill=readable_on_paper(brand), anchor="rm")
        d.text((x0, 200), "Prodotti venduti sfusi al banco · Reg. UE 1169/2011, Allegato II · D.Lgs. 231/2017",
               font=font(40), fill=(80, 84, 96), anchor="lm")
        y = 280
        head_h = 230
        d.rectangle((x0, y, W - 120, y + head_h), fill=mix(brand, WHITE, 0.9))
        d.text((x0 + 20, y + head_h - 30), "Prodotto (banco)", font=font(40, True), fill=INK, anchor="lb")
        for i, c in enumerate(CODES):
            cx = x0 + name_w + i * col_w + col_w // 2
            lab = Image.new("RGBA", (head_h - 20, col_w), (0, 0, 0, 0))
            fs = 34
            while font(fs, True).getlength(SHORT[c]) > head_h - 32 and fs > 20:
                fs -= 2
            ImageDraw.Draw(lab).text((6, col_w // 2), SHORT[c], font=font(fs, True), fill=INK + (255,), anchor="lm")
            lab = lab.rotate(90, expand=True)
            img.paste(lab, (cx - lab.width // 2, y + 10), lab)
        d.text((x0 + name_w + 14 * col_w + 20, y + head_h - 30), "Controllato da", font=font(36, True), fill=INK,
               anchor="lb")
        y += head_h
        row_h = 96
        for it in groups[start:start + rows_per_page]:
            fn, ln = fit_text(f"{it.name} ({COUNTERS.get(it.counter, '')})", name_w - 30, row_h - 10, 38, False, 2,
                              min_size=26)
            ty = y + (row_h - len(ln) * int(fn.size * 1.15)) // 2
            for line in ln:
                d.text((x0 + 20, ty), line, font=fn, fill=INK)
                ty += int(fn.size * 1.15)
            for i, c in enumerate(CODES):
                cx = x0 + name_w + i * col_w + col_w // 2
                if c in (it.allergens or []):
                    d.ellipse((cx - 22, y + row_h // 2 - 22, cx + 22, y + row_h // 2 + 22), fill=INK)
                elif c in (it.may_contain or []):
                    d.ellipse((cx - 20, y + row_h // 2 - 20, cx + 20, y + row_h // 2 + 20), outline=INK, width=5)
            who = it.checked_by + (f" · {it.checked_at:%d/%m/%Y}" if it.checked_at else "")
            fw, lw = fit_text(who, 400, row_h - 10, 30, False, 2, min_size=22)
            d.text((x0 + name_w + 14 * col_w + 20, y + row_h // 2), lw[0], font=fw, fill=(60, 64, 76), anchor="lm")
            d.line((x0, y + row_h, W - 120, y + row_h), fill=(200, 200, 200), width=2)
            y += row_h
        for i in range(15):
            x = x0 + name_w + i * col_w
            d.line((x, 280, x, y), fill=(200, 200, 200), width=2)
        d.rectangle((x0, 280, W - 120, y), outline=(150, 150, 150), width=3)
        d.text((x0, H - 110), "●  contiene        ○  può contenere tracce (dichiarato dal negozio)", font=font(38),
               fill=INK, anchor="lm")
        d.text((W - 120, H - 110), f"Stampato il {datetime.now():%d/%m/%Y} · pagina {len(pages) + 1}", font=font(34),
               fill=(80, 84, 96), anchor="rm")
        pages.append(img)
    out.parent.mkdir(parents=True, exist_ok=True)
    pages[0].save(out, "PDF", resolution=300, save_all=True, append_images=pages[1:])
    return out


def notice_pdf(store: Store, out: Path) -> Path:
    """Il cartello da esporre al banco: le informazioni sugli allergeni sono disponibili per iscritto."""
    W, H = 2480, 3508
    brand = hex_rgb(store.brand_color)
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)
    pad = 160
    d.rectangle((0, 0, W, 520), fill=brand)
    fg = WHITE if sum(brand) < 600 else INK
    ft, lt = fit_text("Allergeni e intolleranze", W - 2 * pad, 220, 170, "display", 1)
    d.text((pad, 260), lt[0], font=ft, fill=fg, anchor="lm")
    y = 640
    for txt, size, bold in [("Le informazioni sugli allergeni di tutti i prodotti del banco sono scritte sui "
                             "cartellini e nel registro degli allergeni.", 76, True),
                            ("Se hai allergie o intolleranze, chiedi al personale prima di acquistare: ti mostriamo "
                             "il registro.", 64, False)]:
        f, lines = fit_text(txt, W - 2 * pad, 600, size, bold, 5)
        for line in lines:
            d.text((pad, y), line, font=f, fill=INK)
            y += int(f.size * 1.3)
        y += 60
    d.text((pad, y + 20), "I 14 allergeni (Reg. UE 1169/2011)", font=font(60, True), fill=readable_on_paper(brand))
    y += 130
    cols = 2
    cw = (W - 2 * pad) // cols
    for i, c in enumerate(CODES):
        cx = pad + (i % cols) * cw
        cy = y + (i // cols) * 150
        d.ellipse((cx, cy + 10, cx + 90, cy + 100), fill=mix(brand, WHITE, 0.85))
        d.text((cx + 45, cy + 55), str(i + 1), font=font(48, True), fill=readable_on_paper(brand), anchor="mm")
        d.text((cx + 120, cy + 55), LABEL[c], font=font(56), fill=INK, anchor="lm")
    d.text((W // 2, H - 140), store.name, font=font(56, True), fill=INK, anchor="mm")
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PDF", resolution=300)
    return out
