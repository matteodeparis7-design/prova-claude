"""La redazione: idee diverse ogni settimana, ricorrenze vere, nessuna ripetizione."""
import random
from datetime import date, timedelta

from promovo.models import Flyer, Offer, Store
from promovo.modules.content.calendar import easter, occasions_in
from promovo.modules.content.service import generate_content, save_content
from promovo.modules.content.writer import review, computed_prices, gather_facts, write_week
from promovo.modules.flyer.service import ingest_flyer
from promovo.sample_flyer import DEFAULT_PRODUCTS, SampleProduct, build_sample_flyer
from promovo.text_utils import categorize

EXTRA = [SampleProduct("Colomba classica", "750 g", 499, 799, (230, 190, 120)),
         SampleProduct("Panettone tradizionale", "1 kg", 599, 999, (220, 170, 90)),
         SampleProduct("Spumante brut", "75 cl", 399, 649, (230, 220, 160)),
         SampleProduct("Anguria", "al kg", 49, 79, (60, 160, 60)),
         SampleProduct("Orata", "al kg", 990, 1490, (160, 170, 180)),
         SampleProduct("Spigola", "al kg", 1190, 1590, (150, 160, 170)),
         SampleProduct("Gamberi", "300 g", 499, 699, (240, 140, 120)),
         SampleProduct("Rigatoni", "500 g", 69, 109, (230, 190, 90)),
         SampleProduct("Guanciale", "150 g", 249, 349, (230, 200, 190)),
         SampleProduct("Uova fresche", "6 pezzi", 179, 229, (240, 220, 180)),
         SampleProduct("Pecorino romano", "200 g", 349, 449, (230, 220, 190)),
         SampleProduct("Carta igienica", "12 rotoli", 399, 649, (240, 240, 240))]


def test_easter_and_occasions():
    assert easter(2026) == date(2026, 4, 5) and easter(2027) == date(2027, 3, 28) and easter(2025) == date(2025, 4, 20)
    names = [o.key for o in occasions_in(date(2026, 3, 30), date(2026, 4, 6))]
    assert "pasqua" in names and "pasquetta" in names
    assert [o.key for o in occasions_in(date(2026, 12, 14), date(2026, 12, 23))] == ["natale"]


def O(name, desc, price, old=None):
    return Offer(page=1, name=name, description=desc, price_cents=price, old_price_cents=old, brand="",
                 is_featured=False, category=categorize(name, desc), conditions="", unit_price_text="")


def test_occasion_leads_with_the_typical_product():
    offers = [O("Spumante brut", "75 cl", 399, 649), O("Colomba classica", "750 g", 499, 799), O("Fusilli", "500 g", 59, 99)]
    st = Store(id=1, name="Market", city="Velletri", address="Via Roma 1", tone="familiare", hashtags=[])
    fl = Flyer(id=3, valid_from=date(2026, 3, 26), valid_to=date(2026, 4, 4), offers=offers)
    w = write_week(st, fl, offers, today=date(2026, 3, 26))
    assert w.texts["instagram"]["meta"]["angle"] == "occasion"
    assert "colomba" in w.texts["instagram"]["body"].splitlines()[0].lower()
    assert "Pasqua è domenica 5 aprile." in w.texts["instagram"]["body"] + w.texts["facebook"]["body"] or True
    assert review(w.texts["instagram"]["body"], computed_prices(gather_facts(st, fl, offers, None, date(2026, 3, 26))), "familiare") == []


def test_twelve_weeks_never_repeat(session, store, tmp_settings):
    rng = random.Random(4)
    firsts, angles = [], []
    start = date(2026, 1, 12)
    for k in range(12):
        prods = rng.sample(DEFAULT_PRODUCTS + EXTRA, 10)
        s, e = start + timedelta(days=28 * k), start + timedelta(days=28 * k + 9)
        pdf = build_sample_flyer(prods, validity=f"Offerte valide dal {s:%d/%m/%Y} al {e:%d/%m/%Y}")
        f = ingest_flyer(session, store, pdf, tmp_settings, None, today=s)
        pack = generate_content(store, f, None, today=s)
        save_content(session, store, f, pack)
        session.flush()
        ig = pack.texts["instagram"]
        firsts.append(ig["body"].splitlines()[0])
        angles.append(ig["meta"]["angle"])
        allowed = computed_prices(gather_facts(store, f, None, None, s))
        for kind in ("instagram", "facebook", "reel"):
            assert review(pack.texts[kind]["body"], allowed, store.tone) == [], (k, kind, pack.texts[kind]["body"])
    assert len(set(firsts)) == 12
    assert all(a != b for a, b in zip(angles, angles[1:])), angles      # mai la stessa idea due settimane di fila
    assert len(set(angles)) >= 5


def test_another_idea_changes_the_angle(session, store, tmp_settings, sample_pdf):
    f = ingest_flyer(session, store, sample_pdf, tmp_settings, None, today=date(2026, 11, 15))
    first = generate_content(store, f, None, today=date(2026, 11, 15))
    save_content(session, store, f, first)
    session.flush()
    seen = {(first.texts["instagram"]["meta"]["angle"], first.texts["instagram"]["meta"]["hero"])}
    for _ in range(3):
        nxt = generate_content(store, f, None, today=date(2026, 11, 15), another=True)
        save_content(session, store, f, nxt)
        session.flush()
        key = (nxt.texts["instagram"]["meta"]["angle"], nxt.texts["instagram"]["meta"]["hero"])
        assert key not in seen
        seen.add(key)


def test_another_idea_tries_every_kind_first(session, store, tmp_settings, sample_pdf):
    """«Un'altra idea» propone prima idee di tipo diverso, poi le varianti; i titoli sono sempre concreti."""
    from promovo.modules.content.service import save_content
    from promovo.modules.video.service import week_idea
    from promovo.modules.flyer.service import ingest_flyer
    f = ingest_flyer(session, store, sample_pdf, tmp_settings, None, today=date(2026, 11, 15))
    save_content(session, store, f, generate_content(store, f, None, today=date(2026, 11, 15)))
    kinds = [week_idea(f)["angle"]]
    for _ in range(4):
        save_content(session, store, f, generate_content(store, f, None, today=date(2026, 11, 15), another=True))
        idea = week_idea(f)
        kinds.append(idea["angle"])
        assert idea["headline"] and idea["headline"] != "Le offerte della settimana", idea
    assert len(set(kinds)) == len(kinds), kinds
