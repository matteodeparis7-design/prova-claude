"""Volantini fatti solo di immagini: OCR, doppia lettura IA e lettura in background."""
import copy

import pymupdf
import pytest

from promovo.models import FlyerStatus
from promovo.modules.flyer.crosscheck import AICheck, crosscheck, ocr_available
from promovo.modules.flyer.extract import extract_heuristic, extract_offers, verify_and_clean, AIMeta, AIPage
from promovo.modules.flyer.pdf import open_pdf
from promovo.modules.flyer.service import create_flyer, process_flyer

from conftest import TODAY


def image_only(pdf: bytes) -> bytes:
    """Trasforma ogni pagina in un'immagine: niente testo, come molti volantini veri."""
    src = pymupdf.open(stream=pdf, filetype="pdf")
    out = pymupdf.open()
    for page in src:
        pix = page.get_pixmap(dpi=150, alpha=False)
        new = out.new_page(width=page.rect.width, height=page.rect.height)
        new.insert_image(new.rect, stream=pix.tobytes("png"))
    return out.tobytes()


@pytest.fixture(scope="module")
def truth(sample_pdf):
    """Offerte corrette lette dal PDF con testo: servono da riferimento."""
    return extract_heuristic(open_pdf(sample_pdf), TODAY).offers


@pytest.fixture(scope="module")
def image_pdf(sample_pdf):
    return image_only(sample_pdf)


needs_ocr = pytest.mark.skipif(not ocr_available(), reason="Tesseract non installato")


def test_image_only_pdf_has_no_text(image_pdf):
    doc = open_pdf(image_pdf)
    assert all(not p.get_text("text").strip() for p in doc)


@needs_ocr
def test_ocr_confirms_right_prices_and_rejects_wrong_ones(image_pdf, truth):
    doc = open_pdf(image_pdf)
    offers = [copy.copy(o) for o in truth]
    for o in offers:
        o.price_verified, o.verified_by = False, ""
    wrong = copy.copy(offers[0])
    wrong.name, wrong.price_cents = "Prezzo sbagliato", 555
    offers.append(wrong)
    crosscheck(offers, doc, None, {1, 2})
    right = [o for o in offers if o is not wrong]
    confirmed = [o for o in right if o.price_verified]
    assert len(confirmed) >= len(right) // 2, "l'OCR deve confermare almeno metà dei prezzi giusti"
    assert all(o.verified_by == "OCR" for o in confirmed)
    assert not wrong.price_verified


def test_ai_double_reading(image_pdf, truth, fake_llm, monkeypatch):
    # Senza OCR, per provare solo la doppia lettura IA.
    monkeypatch.setattr("promovo.modules.flyer.crosscheck.ocr_available", lambda: False)
    doc = open_pdf(image_pdf)
    offers = [copy.copy(o) for o in truth[:3]]
    for o in offers:
        o.price_verified = False
    batches = []

    def second_reading(content):
        n = sum(1 for b in content if b["type"] == "image")
        batches.append(n)
        # 1: concorda, 2: legge un prezzo diverso, 3: illeggibile
        return AICheck.model_validate({"items": [
            {"index": 1, "price": f"{offers[0].price_cents // 100},{offers[0].price_cents % 100:02d}"},
            {"index": 2, "price": "9,99"},
            {"index": 3, "price": None}]})

    fake_llm.on_parse("AICheck", second_reading)
    warnings = crosscheck(offers, doc, fake_llm, {1})
    assert batches == [3]
    assert offers[0].price_verified and offers[0].verified_by == "doppia lettura IA"
    assert not offers[1].price_verified and not offers[2].price_verified
    assert offers[1].price_cents == truth[1].price_cents  # il controllo non cambia mai un prezzo
    assert any("e poi € 9,99" in w for w in warnings)
    assert any("non confermati" in w for w in warnings)


def test_ai_double_reading_unavailable(image_pdf, truth, fake_llm, monkeypatch):
    monkeypatch.setattr("promovo.modules.flyer.crosscheck.ocr_available", lambda: False)
    fake_llm.unavailable = True
    offers = [copy.copy(truth[0])]
    offers[0].price_verified = False
    warnings = crosscheck(offers, open_pdf(image_pdf), fake_llm, {1})
    assert not offers[0].price_verified
    assert any("non completata" in w for w in warnings)


def test_pages_with_text_are_not_rechecked(sample_pdf, fake_llm):
    res = verify_and_clean(extract_heuristic(open_pdf(sample_pdf), TODAY), open_pdf(sample_pdf), fake_llm)
    assert all(o.verified_by == "testo PDF" for o in res.offers)
    assert fake_llm.calls == []


@needs_ocr
def test_full_ai_reading_of_image_flyer(image_pdf, truth, fake_llm):
    """Lettura IA finta di un volantino solo immagini: i prezzi giusti vengono confermati."""
    def page_reading(content):
        page = int(content[1]["text"].split()[1])
        return AIPage.model_validate({"offers": [
            dict(name=o.name, brand="", description=o.description, category=o.category,
                 price=f"{o.price_cents // 100},{o.price_cents % 100:02d}", old_price=None, discount_percent=None,
                 unit_price_text="", conditions="", x0=int(o.bbox[0] * 1000), y0=int(o.bbox[1] * 1000),
                 x1=int(o.bbox[2] * 1000), y1=int(o.bbox[3] * 1000),
                 photo_x0=0, photo_y0=0, photo_x1=0, photo_y1=0)
            for o in truth if o.page == page]})
    fake_llm.on_parse("AIPage", page_reading)
    fake_llm.on_parse("AIMeta", lambda c: AIMeta(title="", store_or_banner="", valid_from=None, valid_to=None))
    fake_llm.on_parse("AICheck", lambda c: AICheck(items=[]))  # la seconda lettura non conferma nulla
    res = extract_offers(open_pdf(image_pdf), fake_llm, TODAY)
    assert len(res.offers) == len(truth)
    assert sum(o.price_verified for o in res.offers) >= len(truth) // 2


def test_process_flyer_failure_leaves_no_offers(session, store, sample_pdf, tmp_settings, monkeypatch):
    flyer = create_flyer(session, store, sample_pdf, tmp_settings)
    assert flyer.status == FlyerStatus.processing and flyer.offers == []

    def boom(*a, **k):
        raise RuntimeError("guasto simulato")
    monkeypatch.setattr("promovo.modules.flyer.service.render_crop", boom)
    flyer = process_flyer(session, flyer, tmp_settings, None, TODAY)
    assert flyer.status == FlyerStatus.failed and "guasto simulato" in flyer.error
    assert flyer.offers == []


def test_process_flyer_missing_file(session, store, sample_pdf, tmp_settings):
    from pathlib import Path
    flyer = create_flyer(session, store, sample_pdf, tmp_settings)
    Path(flyer.pdf_path).unlink()
    flyer = process_flyer(session, flyer, tmp_settings, None, TODAY)
    assert flyer.status == FlyerStatus.failed and "non leggibile" in flyer.error
