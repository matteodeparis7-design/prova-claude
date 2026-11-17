"""Batteria di prove: tanti tipi di volantino, file rotti, casi limite di video e contenuti."""
import copy
import io

import pymupdf
import pytest
from PIL import Image

from promovo.modules.content.service import generate_content
from promovo.modules.flyer.crosscheck import crosscheck, ocr_available
from promovo.modules.flyer.extract import extract_heuristic
from promovo.modules.flyer.pdf import InvalidPDF, MAX_PAGES, normalize_upload, open_pdf
from promovo.modules.flyer.service import ingest_flyer
from promovo.modules.video.render import Renderer
from promovo.modules.video.service import build_spec
from promovo.models import FlyerStatus
from promovo.sample_flyer import DEFAULT_PRODUCTS, FlyerStyle, SampleProduct, build_sample_flyer, make_image_only

from conftest import TODAY

SPECIAL = [
    SampleProduct("Caffè d'orzo solubile", "200 g", 219, 289, (120, 80, 40)),
    SampleProduct("Würstel di pollo", "4 pz", 149, None, (230, 170, 140)),
    SampleProduct("Televisore 55 pollici", "4K", 129900, 149900, (30, 30, 30)),
    SampleProduct("Vino rosso DOC", "0,75 L", 1290, 1590, (120, 20, 40)),
    SampleProduct("Pane", "", 99, None, (220, 180, 120)),
    SampleProduct("Crème caramel", "2 x 100 g", 179, 229, (240, 200, 120)),
]

VARIANTS = {
    "base": dict(),
    "fitto 3x5": dict(style=FlyerStyle(cols=3, rows=5), products=DEFAULT_PRODUCTS * 3),
    "orizzontale 4x4": dict(style=FlyerStyle(cols=4, rows=4, page_size=(1417, 1323)), products=DEFAULT_PRODUCTS * 2),
    "prezzi neri con euro": dict(style=FlyerStyle(price_style="black", euro_sign=True)),
    "prezzi su riquadro": dict(style=FlyerStyle(price_style="badge")),
    "prezzo al kg piccolo": dict(style=FlyerStyle(unit_price=True)),
    "sfondo scuro": dict(style=FlyerStyle(background=(0.1, 0.15, 0.3))),
    "una sola offerta": dict(products=DEFAULT_PRODUCTS[:1]),
    "nomi speciali e prezzi alti": dict(products=SPECIAL),
}


def key(o):
    return (o.name, o.price_cents, o.old_price_cents)


@pytest.mark.parametrize("variant", list(VARIANTS))
def test_text_flyers_read_exactly(variant):
    kw = VARIANTS[variant]
    products = kw.get("products", DEFAULT_PRODUCTS)
    res = extract_heuristic(open_pdf(build_sample_flyer(**kw)), TODAY)
    expected = sorted(((p.name, p.price_cents, p.old_price_cents) for p in products), key=str)
    assert sorted((key(o) for o in res.offers), key=str) == expected


@pytest.mark.skipif(not ocr_available(), reason="Tesseract non installato")
@pytest.mark.parametrize("variant", list(VARIANTS))
def test_image_flyers_ocr_never_confirms_wrong_prices(variant):
    pdf = build_sample_flyer(**VARIANTS[variant])
    truth = extract_heuristic(open_pdf(pdf), TODAY).offers
    img = open_pdf(make_image_only(pdf))
    right = [copy.copy(o) for o in truth]
    wrong = [copy.copy(o) for o in truth[:3]]
    for o in right:
        o.price_verified = False
    for o in wrong:
        o.price_cents += 10   # una cifra sbagliata, l'errore più insidioso
        o.price_verified = False
    crosscheck(right + wrong, img, None, set(range(1, img.page_count + 1)))
    assert not any(o.price_verified for o in wrong), "un prezzo sbagliato non deve mai essere confermato"
    assert sum(o.price_verified for o in right) >= 0.8 * len(right)


# ------------------------------------------------------------------ file di ogni tipo

def _image_bytes(fmt: str) -> bytes:
    pdf = open_pdf(build_sample_flyer(DEFAULT_PRODUCTS[:6]))
    pix = pdf[0].get_pixmap(dpi=100, alpha=False)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format=fmt)
    return buf.getvalue()


@pytest.mark.parametrize("fmt", ["JPEG", "PNG", "WEBP"])
def test_image_uploads_become_pdf(fmt):
    pdf = normalize_upload(_image_bytes(fmt))
    doc = open_pdf(pdf)
    assert doc.page_count == 1 and not doc[0].get_text("text").strip()


def _encrypted_pdf() -> bytes:
    doc = pymupdf.open()
    doc.new_page()
    return doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="segreto", owner_pw="segreto")


def _too_many_pages() -> bytes:
    doc = pymupdf.open()
    for _ in range(MAX_PAGES + 1):
        doc.new_page(width=100, height=100)
    return doc.tobytes()


@pytest.mark.parametrize("data,msg", [
    (b"", "vuoto"),
    (b"GIF89a....", "Formato non supportato"),
    (b"\xff\xd8\xff\xe0 jpeg rotto", "danneggiata"),
    (b"%PDF-1.7\nspazzatura", "danneggiato"),
    (b"PK\x03\x04 un file zip", "Formato non supportato"),
])
def test_bad_files_are_refused_clearly(data, msg):
    with pytest.raises(InvalidPDF, match=msg):
        open_pdf(normalize_upload(data))


def test_encrypted_and_too_long_pdfs():
    with pytest.raises(InvalidPDF, match="password"):
        open_pdf(_encrypted_pdf())
    with pytest.raises(InvalidPDF, match="pagine"):
        open_pdf(_too_many_pages())


def test_image_flyer_ingest_without_ai(session, store, tmp_settings):
    flyer = ingest_flyer(session, store, _image_bytes("JPEG"), tmp_settings, None, today=TODAY)
    assert flyer.status == FlyerStatus.ready and flyer.offers == []
    assert any("serve l'IA" in w for w in flyer.warnings)


def test_flyer_without_offers_or_dates(session, store, tmp_settings):
    doc = pymupdf.open()
    doc.new_page().insert_text((50, 100), "Auguri di buone feste da tutto lo staff!", fontsize=20)
    flyer = ingest_flyer(session, store, doc.tobytes(), tmp_settings, None, today=TODAY)
    assert flyer.status == FlyerStatus.ready and flyer.offers == []
    assert flyer.valid_from is None
    pack = generate_content(store, flyer, None)
    assert pack.warnings == ["Nessuna offerta nel volantino."]


# ------------------------------------------------------------------ video, casi limite

@pytest.fixture
def big_flyer(session, store, tmp_settings):
    pdf = build_sample_flyer((DEFAULT_PRODUCTS + SPECIAL) * 3, style=FlyerStyle(cols=3, rows=4))
    return ingest_flyer(session, store, pdf, tmp_settings, None, today=TODAY)


def test_video_limits_offer_count(store, big_flyer):
    assert len(big_flyer.offers) == 54
    assert len(build_spec(store, big_flyer, "landscape").offers) == 40
    assert len(build_spec(store, big_flyer, "portrait").offers) == 6
    assert len(build_spec(store, big_flyer, "square").offers) == 6


@pytest.mark.parametrize("brand,accent", [("#FFFF00", "#FFFFFF"), ("#000000", "#000000"), ("#7F7F7F", "#00FF00")])
def test_video_any_colors(store, big_flyer, brand, accent):
    store.brand_color, store.accent_color = brand, accent
    spec = build_spec(store, big_flyer, "square", scale=0.3, max_offers=1)
    r = Renderer(spec)
    for t in (0.2, 4.0, r.duration - 0.1):
        assert r.frame_at(t).size == (r.W, r.H)


def test_video_missing_images_and_validity(store, big_flyer):
    for o in big_flyer.offers:
        o.crop_path = "/non/esiste.png"
    big_flyer.valid_from = big_flyer.valid_to = None
    spec = build_spec(store, big_flyer, "portrait", scale=0.3)
    assert spec.validity == ""
    r = Renderer(spec)
    assert r.frame_at(5.0).size == (r.W, r.H)


def test_video_high_prices_and_symbols(store, big_flyer):
    spec = build_spec(store, big_flyer, "landscape", scale=0.3)
    tv = next(o for o in spec.offers if o.price_cents == 129900)
    spec.offers = [tv]
    tv.name = "Televisore 55\" 4K – offerta «speciale» 100% ✓"
    r = Renderer(spec)
    assert r.frame_at(4.0).size == (r.W, r.H)


def test_video_without_system_ffmpeg(store, big_flyer, tmp_path, monkeypatch):
    """Su Windows e Mac spesso ffmpeg non c'è: si usa quello incluso nel pacchetto."""
    import shutil as _shutil
    from promovo.modules.video.render import probe_duration, render_video
    real_which = _shutil.which
    monkeypatch.setattr("promovo.modules.video.render.shutil.which",
                        lambda name: None if name in ("ffmpeg", "ffprobe") else real_which(name))
    spec = build_spec(store, big_flyer, "square", scale=0.25, max_offers=1)
    spec.intro_seconds = spec.outro_seconds = spec.offer_seconds = 1.0
    out = render_video(spec, tmp_path / "v.mp4", preset="ultrafast")
    assert abs(probe_duration(out) - 3.0) < 0.2
