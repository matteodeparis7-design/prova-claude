from pathlib import Path

from promovo import pdfdoc
import pytest

from promovo.modules.flyer.extract import AIMeta, AIPage, extract_offers, pick_featured
from promovo.modules.flyer.pdf import InvalidPDF, open_pdf
from promovo.modules.flyer.service import delete_flyer_files, ingest_flyer
from promovo.models import FlyerStatus
from promovo.sample_flyer import DEFAULT_PRODUCTS

from conftest import TODAY


def expected():
    return {(p.name, p.price_cents, p.old_price_cents) for p in DEFAULT_PRODUCTS}


def test_heuristic_reads_every_offer(sample_pdf):
    res = extract_offers(open_pdf(sample_pdf), None, TODAY)
    assert res.method == "heuristic"
    assert {(o.name, o.price_cents, o.old_price_cents) for o in res.offers} == expected()
    assert all(o.price_verified for o in res.offers)
    assert res.valid_from.isoformat() == "2026-11-13" and res.valid_to.isoformat() == "2026-11-22"
    assert res.title == "SUPERSTORE"
    for o in res.offers:
        x0, y0, x1, y1 = o.bbox
        assert 0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1
    pasta = next(o for o in res.offers if o.name.startswith("Spaghetti"))
    assert pasta.description == "500 g" and pasta.discount_percent == 39 and pasta.category == "pasta e riso"


def _ai_pages(content):
    """Risposta IA finta: legge il numero di pagina dal testo e restituisce offerte coerenti."""
    text = content[-1]["text"]
    page = int(text.split()[1])
    if page == 1:
        return AIPage.model_validate({"offers": [
            dict(name="Spaghetti di grano duro", brand="", description="500 g", category="pasta e riso",
                 price="0,79", old_price="1,29", discount_percent=39, unit_price_text="", conditions="",
                 x0=30, y0=120, x1=480, y1=330, photo_x0=40, photo_y0=130, photo_x1=270, photo_y1=260),
            # prezzo inventato: deve risultare "da controllare"
            dict(name="Passata di pomodoro", brand="", description="700 g", category="dispensa",
                 price="0,95", old_price=None, discount_percent=None, unit_price_text="", conditions="",
                 x0=520, y0=120, x1=980, y1=330, photo_x0=0, photo_y0=0, photo_x1=1000, photo_y1=1000),
            # riquadro degenere: deve essere scartata
            dict(name="Fantasma", brand="", description="", category="altro", price="1,00", old_price=None,
                 discount_percent=None, unit_price_text="", conditions="", x0=10, y0=10, x1=10, y1=10,
                 photo_x0=10, photo_y0=10, photo_x1=10, photo_y1=10),
            # prezzo barrato non presente nel PDF: va tolto, insieme allo sconto calcolato
            dict(name="Mozzarella fior di latte", brand="", description="125 g", category="salumi e formaggi",
                 price="0,89", old_price="1,50", discount_percent=None, unit_price_text="", conditions="",
                 x0=30, y0=420, x1=480, y1=620, photo_x0=40, photo_y0=430, photo_x1=270, photo_y1=560),
        ]})
    return AIPage(offers=[])


def test_ai_extraction_with_verification(sample_pdf, fake_llm):
    fake_llm.on_parse("AIPage", _ai_pages)
    fake_llm.on_parse("AIMeta", lambda c: AIMeta(title="Volantino novembre", store_or_banner="Superstore",
                                                 valid_from="2026-11-13", valid_to="2026-11-22"))
    res = extract_offers(open_pdf(sample_pdf), fake_llm, TODAY)
    assert res.method == "ai"
    names = {o.name: o for o in res.offers}
    assert set(names) == {"Spaghetti di grano duro", "Passata di pomodoro", "Mozzarella fior di latte"}
    assert names["Spaghetti di grano duro"].price_verified
    assert names["Spaghetti di grano duro"].photo_bbox == [0.04, 0.13, 0.27, 0.26]
    assert names["Passata di pomodoro"].photo_bbox is None   # foto fuori dal riquadro: scartata
    assert not names["Passata di pomodoro"].price_verified
    assert names["Mozzarella fior di latte"].old_price_cents is None
    assert names["Mozzarella fior di latte"].discount_percent is None
    assert any("scartate" in w for w in res.warnings)
    assert any("non trovati" in w for w in res.warnings)
    assert res.title == "Volantino novembre"


def test_ai_unavailable_falls_back(sample_pdf, fake_llm):
    fake_llm.unavailable = True
    res = extract_offers(open_pdf(sample_pdf), fake_llm, TODAY)
    assert res.method == "heuristic"
    assert len(res.offers) == len(DEFAULT_PRODUCTS)
    assert "IA facoltativa non disponibile" in res.warnings[0]


def test_ai_bad_dates_are_dropped(sample_pdf, fake_llm):
    fake_llm.on_parse("AIPage", lambda c: AIPage(offers=[]))
    fake_llm.on_parse("AIMeta", lambda c: AIMeta(title="", store_or_banner="", valid_from="2026-12-01",
                                                 valid_to="2026-11-01"))
    res = extract_offers(open_pdf(sample_pdf), fake_llm, TODAY)
    assert res.valid_from is None and res.valid_to is None
    assert "Nessuna offerta trovata nel volantino." in res.warnings


@pytest.mark.parametrize("data,msg", [
    (b"ciao", "non è un PDF"),
    (b"%PDF-1.4 rotto", "danneggiato"),
])
def test_invalid_pdf(data, msg):
    with pytest.raises(InvalidPDF, match=msg):
        open_pdf(data)


def test_image_only_page_warns():
    doc = pdfdoc.open()
    doc.new_page()
    data = doc.tobytes()
    res = extract_offers(open_pdf(data), None, TODAY)
    assert res.offers == []
    assert any("nessuna offerta riconosciuta" in w or "solo di immagini" in w for w in res.warnings)


def test_ingest_and_delete(session, store, sample_pdf, tmp_settings):
    flyer = ingest_flyer(session, store, sample_pdf, tmp_settings, None, today=TODAY)
    assert flyer.status == FlyerStatus.ready
    assert len(flyer.offers) == len(DEFAULT_PRODUCTS)
    assert sum(o.is_featured for o in flyer.offers) == 6
    for o in flyer.offers:
        assert Path(o.crop_path).exists()
        # La foto del prodotto è separata, scontornata (trasparente) e senza il prezzo.
        assert o.photo_path and Path(o.photo_path).exists()
        from PIL import Image
        with Image.open(o.photo_path) as ph:
            assert ph.mode == "RGBA" and ph.getchannel("A").getextrema()[0] == 0
    assert Path(flyer.pdf_path).read_bytes() == sample_pdf
    # Lo stesso PDF caricato due volte crea due volantini indipendenti.
    flyer2 = ingest_flyer(session, store, sample_pdf, tmp_settings, None, today=TODAY)
    delete_flyer_files(flyer, tmp_settings)
    assert not Path(flyer.pdf_path).exists()
    assert Path(flyer2.pdf_path).exists()
    assert all(Path(o.crop_path).exists() for o in flyer2.offers)


def test_ingest_too_big(session, store, sample_pdf, tmp_settings):
    from dataclasses import replace
    small = replace(tmp_settings, max_upload_mb=0)
    with pytest.raises(InvalidPDF, match="supera"):
        ingest_flyer(session, store, sample_pdf, small, None)


def test_pick_featured_prefers_discounts(sample_pdf):
    res = extract_offers(open_pdf(sample_pdf), None, TODAY)
    idx = pick_featured(res.offers, 2)
    best = sorted(res.offers, key=lambda o: -(o.discount_percent or 0))[:2]
    assert {res.offers[i].name for i in idx} == {o.name for o in best}
