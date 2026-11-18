"""Agente Lettore senza IA: come capisce le righe lette dalla lettura ottica."""
import pytest

from promovo.modules.flyer import ocr
from promovo.modules.flyer.ocr import Line, classify, fix_accents, lines_to_offers, nice_name, split_format, split_glued


@pytest.mark.parametrize("raw,want", [
    ("GAMBERO ROSA NAZIONALE", "Gambero rosa nazionale"),
    ("LIMONIDISORRENTO IGP", "Limoni di sorrento IGP"),
    ("CARCIOFIMAMMOLE", "Carciofi mammole"),
    ("FIORUCCISALAME CORALLINA", "Fiorucci salame corallina"),
    ("CALÀMARO DEC.", "Calamaro dec."),
    ("FILETTO DI BACCALÀ", "Filetto di baccalà"),
    ("Mozzarella fior di latte", "Mozzarella fior di latte"),
])
def test_nice_names(raw, want):
    assert nice_name(raw) == want


def test_accents_and_glued_words():
    assert fix_accents("MELÉ") == "MELE" and fix_accents("CAFFÈ") == "CAFFÈ" and fix_accents("perché") == "perché"
    assert split_glued("VONGOLELUPINO") == "VONGOLE LUPINO"
    assert split_glued("superstore") == "superstore"          # parola sconosciuta: si lascia com'è


@pytest.mark.parametrize("raw,name,fmt", [
    ("ASPARAGI 500g", "ASPARAGI", "500 g"),
    ("SPIGOLA300/700", "SPIGOLA", "300/700"),
    ("SPINACI g 250", "SPINACI", "250 g"),
    ("COCA COLA FOURPACK 4x1.501", "COCA COLA FOURPACK", "4 x 1.50 l"),
    ("Olio extravergine di oliva 1 litro", "Olio extravergine di oliva", "1 litro"),
])
def test_split_format(raw, name, fmt):
    assert split_format(raw) == (name, fmt)


@pytest.mark.parametrize("text,kind,cents", [
    ("€ 1,99", "price", 199), ("e12,99", "price", 1299), (".1,49", "price", 149), ("c6,99", "price", 699),
    ("al kg 7,98", "unit", None), ("alkg", "unit", None), ("500g", "format", None),
    ("Offerte valide dal 13 al 22 novembre", "noise", None), ("Pagina 1", "noise", None),
    ("PATATINE PULITE", "name", None),
])
def test_classify(text, kind, cents):
    ln = Line(text, 0, 0, 0.1, 0.02, 0.99)
    classify(ln)
    assert ln.kind == kind and ln.cents == cents


def L(text, x0, y0, x1, y1):
    return Line(text, x0, y0, x1, y1, 0.99)


def test_name_above_price_on_more_lines():
    lines = [L("GAMBERO ROSA", 0.30, 0.20, 0.40, 0.215), L("NAZIONALE", 0.32, 0.217, 0.40, 0.232),
             L("al kg", 0.37, 0.235, 0.40, 0.245), L("€ 6,99", 0.30, 0.25, 0.40, 0.31),
             L("ALICI", 0.70, 0.20, 0.76, 0.215), L("€ 3,99", 0.68, 0.25, 0.78, 0.31)]
    offers = lines_to_offers(lines, 1)
    got = {o.name: o.price_cents for o in offers}
    assert got == {"Gambero rosa nazionale": 699, "Alici": 399}
    assert next(o for o in offers if o.name.startswith("Gambero")).description == "al kg"


def test_name_below_price_layout():
    lines = [L("1,29", 0.30, 0.16, 0.35, 0.18), L("0,79", 0.30, 0.19, 0.43, 0.24),
             L("Spaghetti di grano duro", 0.05, 0.28, 0.31, 0.30), L("500 g", 0.05, 0.305, 0.10, 0.325),
             L("0,99", 0.76, 0.19, 0.90, 0.24), L("Passata di pomodoro", 0.52, 0.28, 0.75, 0.30)]
    offers = lines_to_offers(lines, 1)
    got = {o.name: (o.price_cents, o.old_price_cents) for o in offers}
    assert got == {"Spaghetti di grano duro": (79, 129), "Passata di pomodoro": (99, None)}


def test_uppercase_name_wins_over_lowercase_variants():
    lines = [L("UOVO KINDER G.", 0.21, 0.80, 0.28, 0.815), L("SORPRESA 150 g", 0.21, 0.817, 0.28, 0.832),
             L("mickey and friend-", 0.20, 0.834, 0.28, 0.848), L("barbie-hot wheels-", 0.20, 0.849, 0.28, 0.862),
             L("€ 11,99", 0.20, 0.87, 0.285, 0.92)]
    o = lines_to_offers(lines, 1)[0]
    assert (o.name, o.description, o.price_cents) == ("Uovo kinder g. sorpresa", "150 g", 1199)


def test_available_flag_is_boolean():
    assert isinstance(ocr.available(), bool)
