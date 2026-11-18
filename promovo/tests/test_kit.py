"""Grafiche, musica, video con audio, pacchetto della settimana e ZIP."""
import io
import subprocess
import zipfile

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from promovo.api import create_app
from promovo.db import Database
from promovo.modules.flyer.service import ingest_flyer
from promovo.modules.graphics.service import grid_image, offer_image, render_flyer_images
from promovo.modules.video.music import compose
from promovo.modules.video.render import ffmpeg_path, render_video
from promovo.modules.video.service import build_spec, store_contacts, whatsapp_link

from conftest import TODAY, FakeLLM, make_store, register, upload


@pytest.fixture
def flyer(session, store, sample_pdf, tmp_settings):
    return ingest_flyer(session, store, sample_pdf, tmp_settings, None, today=TODAY)


def test_music_is_clean_and_exact():
    x = compose(7.5, transitions=[2.0, 4.0], pops=[2.5])
    assert x.shape == (int(7.5 * 44100), 2)
    assert np.isfinite(x).all() and 0.5 < np.abs(x).max() <= 0.9
    assert np.abs(x[:100]).max() < 0.05          # attacco senza scatti
    assert np.abs(x[-100:]).max() < 0.05         # chiusura sfumata


def test_video_with_music_has_audio(store, flyer, tmp_path):
    spec = build_spec(store, flyer, "square", scale=0.3, max_offers=1, music=True)
    spec.intro_seconds = spec.offer_seconds = spec.outro_seconds = 1.0
    out = render_video(spec, tmp_path / "m.mp4", preset="ultrafast")
    info = subprocess.run([ffmpeg_path(), "-hide_banner", "-i", str(out)], capture_output=True, text=True).stderr
    assert "Audio: aac" in info and "Video: h264" in info


def test_contacts_and_qr(store):
    assert whatsapp_link("333 123 4567") == "https://wa.me/393331234567"
    assert whatsapp_link("+39 333 1234567") == "https://wa.me/393331234567"
    assert whatsapp_link("") == ""
    store.whatsapp = "333 1234567"
    lines, qr, label = store_contacts(store)
    assert qr == "https://wa.me/393331234567" and "WhatsApp 333 1234567" in lines and label
    store.website = "esempio.it"
    assert store_contacts(store)[1] == "https://esempio.it"


def test_graphics(session, store, flyer, tmp_settings):
    cover = grid_image(store, flyer, "cover")
    story = grid_image(store, flyer, "story")
    single = offer_image(store, flyer, 0)
    assert cover.size == (1080, 1350) and story.size == (1080, 1920) and single.size == (1080, 1080)
    # Un'immagine vera, non vuota: tanti colori diversi.
    assert len(cover.getcolors(1_000_000) or []) > 500
    pieces = render_flyer_images(session, store, flyer, tmp_settings)
    assert len(pieces) == 8
    again = render_flyer_images(session, store, flyer, tmp_settings)   # rigenerare non duplica
    assert len(again) == 8
    from promovo.models import ContentPiece
    assert session.query(ContentPiece).filter_by(flyer_id=flyer.id, kind="image").count() == 8


def test_graphics_with_light_brand_color(session, store, flyer):
    store.brand_color, store.accent_color = "#FFF6A0", "#FFFFFF"
    img = grid_image(store, flyer, "cover")
    assert img.size == (1080, 1350)


@pytest.fixture
def client(tmp_settings):
    app = create_app(tmp_settings, llm=FakeLLM(), db=Database("sqlite://"))
    with TestClient(app) as c:
        yield c


def test_kit_and_zip(client, live_pdf):
    h = register(client)
    s = make_store(client, h)
    f = upload(client, h, s["id"], live_pdf)
    assert client.post(f"/api/flyers/{f['id']}/kit", headers=h, json={"items": ["boh"]}).status_code == 422
    r = client.post(f"/api/flyers/{f['id']}/kit", headers=h, json={"items": ["texts", "images", "video_square"]})
    assert r.status_code == 202
    job = client.get(f"/api/jobs/{r.json()['id']}", headers=h).json()
    assert job["status"] == "done", job
    assert job["result"]["done"] == ["texts", "images", "video_square"] and job["result"]["errors"] == []
    content = client.get(f"/api/flyers/{f['id']}/content", headers=h).json()
    kinds = sorted({c["kind"] for c in content})
    assert kinds == ["facebook", "image", "instagram", "plan", "video"]
    img = next(c for c in content if c["kind"] == "image")
    got = client.get(img["file_url"], headers=h)
    assert got.headers["content-type"] == "image/jpeg" and Image.open(io.BytesIO(got.content)).size[0] == 1080

    # Rigenerare i testi non crea doppioni.
    client.post(f"/api/flyers/{f['id']}/content", headers=h)
    content = client.get(f"/api/flyers/{f['id']}/content", headers=h).json()
    assert sum(1 for c in content if c["kind"] == "instagram") == 1

    z = client.get(f"/api/flyers/{f['id']}/kit.zip", headers=h)
    assert z.status_code == 200 and z.headers["content-type"] == "application/zip"
    names = zipfile.ZipFile(io.BytesIO(z.content)).namelist()
    assert any(n.endswith("LEGGIMI.txt") for n in names)
    assert any("/Video/" in n and n.endswith(".mp4") for n in names)
    assert sum("/Immagini/" in n for n in names) == 8
    assert any(n.endswith("Testi/Instagram.txt") for n in names)
    # Solo i contenuti approvati.
    z2 = client.get(f"/api/flyers/{f['id']}/kit.zip?approved_only=true", headers=h)
    assert [n for n in zipfile.ZipFile(io.BytesIO(z2.content)).namelist() if not n.endswith(("LEGGIMI.txt", "Piano_della_settimana.txt"))] == []
    # Il file temporaneo dello ZIP viene cancellato dopo l'invio.
    renders = client.app.state.promovo.settings.data_dir / "renders"
    assert not list(renders.glob("pacchetto_*.zip"))


def test_video_poster_endpoint(client, live_pdf):
    h = register(client)
    s = make_store(client, h)
    f = upload(client, h, s["id"], live_pdf)
    client.post(f"/api/flyers/{f['id']}/kit", headers=h, json={"items": ["video_square"]})
    v = next(c for c in client.get(f"/api/flyers/{f['id']}/content", headers=h).json() if c["kind"] == "video")
    assert v["poster_url"]
    p = client.get(v["poster_url"], headers=h)
    assert p.status_code == 200 and p.headers["content-type"] == "image/jpeg"
    # Rifare lo stesso video lo sostituisce: un solo video per formato.
    client.post(f"/api/flyers/{f['id']}/kit", headers=h, json={"items": ["video_square"]})
    vids = [c for c in client.get(f"/api/flyers/{f['id']}/content", headers=h).json() if c["kind"] == "video"]
    assert len(vids) == 1


def test_demo_seed(tmp_settings):
    from promovo.demo import seed_demo
    from promovo.models import Store
    db = Database("sqlite://")
    db.create_all()
    assert seed_demo(db, tmp_settings) is True
    assert seed_demo(db, tmp_settings) is False          # una sola volta
    with db.session() as ses:
        st = ses.get(Store, 1)
        assert st.logo_path and len(st.flyers[0].offers) == 12
        assert all(o.photo_path and o.price_verified for o in st.flyers[0].offers)
