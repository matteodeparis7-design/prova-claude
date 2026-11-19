"""Agenti aggiuntivi: sottotitoli a tempo di parola (Whisper) e scontorno dei prodotti (BiRefNet).

I modelli veri non servono qui: si sostituiscono con finti prevedibili. Si controllano le regole di Promovo
(testo esatto, tempi, sicurezza dei file scaricati, ripiego quando l'agente non c'è)."""
from __future__ import annotations

import hashlib
import io

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from promovo import cutout, extras
from promovo.api import create_app
from promovo.db import Database
from promovo.modules.clip import transcribe as tr
from promovo.modules.clip.service import make_reel
from promovo.modules.video import service as vs

from conftest import TODAY, FakeLLM, register


# ---------------------------------------------------------------- sottotitoli

def W(text, a, b):
    return tr.Word(text, a, b)


HEARD = [W("Buongiorno", 0.0, 0.5), W("a", 0.5, 0.6), W("tutti,", 0.6, 0.9), W("questa", 1.3, 1.5),
         W("settimana", 1.5, 1.9), W("il", 1.9, 2.0), W("sammone", 2.0, 2.4), W("affumicato", 2.4, 3.0),
         W("a", 3.0, 3.1), W("3,49€.", 3.1, 3.8), W("Passate", 4.6, 5.0), W("a", 5.0, 5.1), W("trovarci!", 5.1, 5.7)]
SCRIPT = "Buongiorno a tutti, questa settimana il salmone affumicato a € 3,49. Passate a trovarci!"


def test_align_keeps_the_exact_text_with_real_times():
    words = tr.align(SCRIPT, HEARD)
    assert words is not None
    assert " ".join(w.text for w in words) == SCRIPT                 # niente «sammone»: il testo è quello letto
    t = {w.text: (w.start, w.end) for w in words}
    assert t["Buongiorno"] == (0.0, 0.5) and t["Passate"] == (4.6, 5.0)
    assert 2.0 <= t["salmone"][0] < 2.4                              # parola letta diversa: tempo del tratto
    assert all(a.start <= b.start for a, b in zip(words, words[1:]))


def test_align_refuses_when_the_speaker_said_something_else():
    assert tr.align("Oggi parliamo di tutt'altro argomento davvero diverso", HEARD) is None


def test_timed_captions_break_on_sentences_pauses_and_length():
    caps = tr.timed_captions(tr.align(SCRIPT, HEARD))
    texts = [c[0] for c in caps]
    assert all(len(t) <= 30 for t in texts)
    assert texts[-1] == "Passate a trovarci!"                         # nuova frase dopo la pausa
    assert caps[0][1] == 0.0 and all(a < b for _, a, b in caps)
    assert all(caps[i][2] <= caps[i + 1][1] + 1e-9 for i in range(len(caps) - 1))   # niente sovrapposizioni


def _voice_wav(seconds: float) -> bytes:
    import wave
    sr = 16000
    t = np.arange(int(sr * seconds)) / sr
    x = (0.3 * np.sin(2 * np.pi * 180 * t) * (np.sin(2 * np.pi * 2 * t) > -0.2) * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(x.tobytes())
    return buf.getvalue()


@pytest.fixture
def flyer(session, store, sample_pdf, tmp_settings):
    from promovo.modules.flyer.service import ingest_flyer
    return ingest_flyer(session, store, sample_pdf, tmp_settings, None, today=TODAY)


from test_clip import footage  # noqa: E402,F401  (video «da telefono» di prova)


def test_reel_uses_word_timed_subtitles(session, store, flyer, footage, tmp_settings, tmp_path, monkeypatch):
    calls = {}

    def fake_transcribe(path, hint=""):
        calls["hint"] = hint
        return list(HEARD)
    monkeypatch.setattr(tr, "transcribe", fake_transcribe)
    voice = tmp_path / "voce.wav"
    voice.write_bytes(_voice_wav(6.0))
    # letto il testo proposto: sottotitoli = testo esatto, tempi veri
    piece = make_reel(session, store, tmp_settings, None, footage, offer_id=flyer.offers[0].id, voice_mode="recorded",
                      voice_file=voice, today=TODAY, spoken_script=SCRIPT)
    assert piece.meta["subtitles"] == "a tempo di parola" and piece.meta["script"] == SCRIPT
    # a braccio: sottotitoli e testo del post = quello che ha detto; i nomi dei prodotti aiutano la trascrizione
    voice2 = tmp_path / "voce2.wav"
    voice2.write_bytes(_voice_wav(6.0))
    piece2 = make_reel(session, store, tmp_settings, None, footage, offer_id=flyer.offers[0].id, voice_mode="recorded",
                       voice_file=voice2, today=TODAY)
    assert piece2.meta["subtitles"] == "a tempo di parola" and piece2.meta["script"].startswith("Buongiorno a tutti,")
    assert flyer.offers[0].name.lower() in calls["hint"]


def test_reel_without_the_agent_keeps_estimated_subtitles(session, store, flyer, footage, tmp_settings, tmp_path,
                                                         monkeypatch):
    monkeypatch.setattr(tr, "transcribe", lambda path, hint="": None)
    voice = tmp_path / "voce.wav"
    voice.write_bytes(_voice_wav(6.0))
    piece = make_reel(session, store, tmp_settings, None, footage, offer_id=flyer.offers[0].id, voice_mode="recorded",
                      voice_file=voice, today=TODAY, spoken_script=SCRIPT)
    assert piece.meta["subtitles"] == "stimati" and piece.meta["script"] == SCRIPT


# ---------------------------------------------------------------- scontorno

def _product_photo() -> Image.Image:
    img = Image.new("RGB", (400, 300), (240, 240, 250))
    img.paste((200, 30, 30), (120, 60, 280, 260))          # il prodotto
    img.paste((20, 20, 20), (10, 10, 40, 20))              # una scritta piccola staccata
    return img


def _mask_of(img: Image.Image) -> np.ndarray:
    a = np.asarray(img.convert("RGB")).astype(int)
    return (np.abs(a - np.array([240, 240, 250])).sum(axis=2) > 60).astype(np.float32)


def test_cut_keeps_the_product_and_drops_stray_text(monkeypatch):
    monkeypatch.setattr(cutout, "mask", _mask_of)
    out = cutout.cut(_product_photo())
    assert out is not None and out.mode == "RGBA"
    assert 160 <= out.width <= 185 and 200 <= out.height <= 225   # stretto sul prodotto, la scritta è fuori
    alpha = np.asarray(out)[..., 3]
    assert alpha[out.height // 2, out.width // 2] > 240 and alpha[2, 2] < 30


def test_cut_refuses_unreliable_masks(monkeypatch):
    monkeypatch.setattr(cutout, "mask", lambda img: np.ones((img.height, img.width), np.float32))
    assert cutout.cut(_product_photo()) is None                  # «tutta la foto»: non è uno scontorno
    monkeypatch.setattr(cutout, "mask", lambda img: np.full((img.height, img.width), 0.5, np.float32))
    assert cutout.cut(_product_photo()) is None                  # maschera incerta


def test_offer_image_prefers_own_photo_then_cutout(session, store, flyer, monkeypatch, tmp_path):
    o = flyer.offers[0]
    monkeypatch.setattr(cutout, "available", lambda: True)
    monkeypatch.setattr(cutout, "mask", _mask_of)
    _product_photo().save(o.crop_path)
    img = vs.offer_image(o)
    assert img.endswith("_cut.png")
    assert vs.offer_image(o, cut=False) == img                    # già pronto: lo usano anche i video lunghi
    o2 = flyer.offers[1]
    assert vs.offer_image(o2, cut=False) != (o2.crop_path[:-4] + "_cut.png")   # non pronto: niente attesa
    manual = tmp_path / "manuale_1.png"
    _product_photo().save(manual)
    o.photo_path = str(manual)
    assert vs.offer_image(o) == str(manual)                       # la foto caricata da te vince sempre
    # foto non scontornabile: si segna e non si riprova ogni volta
    monkeypatch.setattr(cutout, "cut", lambda im, text="": None)
    o3 = flyer.offers[2]
    assert not vs.offer_image(o3).endswith("_cut.png")
    assert (o3.crop_path[:-4] + "_cut.no") and __import__("os").path.exists(o3.crop_path[:-4] + "_cut.no")


def test_cutout_can_be_switched_off(monkeypatch):
    monkeypatch.setenv("PROMOVO_CUTOUT", "off")
    assert cutout.available() is False


# ---------------------------------------------------------------- scaricamento sicuro

def _fake_extra(data: bytes, sha: str | None = None) -> extras.Extra:
    return extras.Extra(key="prova", title="Prova", what="", license="MIT", folder="prova",
                        files=(extras.ModelFile("https://esempio/prova.bin", "prova.bin",
                                                sha or hashlib.sha256(data).hexdigest(), len(data)),))


def test_download_checks_the_fingerprint(tmp_path, monkeypatch):
    data = b"modello" * 1000
    extras.set_data_dir(tmp_path)
    monkeypatch.setitem(extras.EXTRAS, "prova", _fake_extra(data))
    opener = lambda url: io.BytesIO(data)                         # noqa: E731
    assert extras.path("prova") is None
    folder = extras.download("prova", opener)
    assert (folder / "prova.bin").read_bytes() == data and extras.path("prova") == folder
    st = next(x for x in extras.status() if x["key"] == "prova")
    assert st["ready"] and not st["bundled"]
    extras.remove("prova")
    assert extras.path("prova") is None
    # file alterato: scartato, niente resta sul disco
    monkeypatch.setitem(extras.EXTRAS, "prova", _fake_extra(data, sha="0" * 64))
    with pytest.raises(RuntimeError, match="non corrisponde"):
        extras.download("prova", opener)
    assert not list((tmp_path / "models" / "prova").glob("*"))
    assert next(x for x in extras.status() if x["key"] == "prova")["error"]


def test_api_extras(tmp_settings):
    app = create_app(tmp_settings, llm=FakeLLM(), db=Database("sqlite://"))
    got = []
    app.state.promovo.extras_download = lambda key: got.append(key)
    with TestClient(app) as c:
        h = register(c)
        lst = c.get("/api/extras", headers=h).json()
        assert {x["key"] for x in lst} == {"cutout", "subtitles"}
        sub = next(x for x in lst if x["key"] == "subtitles")
        assert sub["size_mb"] > 400 and "MIT" in sub["license"]
        assert c.post("/api/extras/subtitles/download", headers=h).status_code == 202
        import time
        for _ in range(50):
            if got:
                break
            time.sleep(0.02)
        assert got == ["subtitles"]
        assert c.post("/api/extras/boh/download", headers=h).status_code == 404
