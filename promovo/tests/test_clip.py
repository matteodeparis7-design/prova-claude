"""Dal banco al Reel: analisi del video, scelta dei tratti, testi sicuri, voce e montaggio."""
from __future__ import annotations

import io
import subprocess
import wave
from pathlib import Path

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

from promovo import voice as voicemod
from promovo.api import create_app
from promovo.db import Database
from promovo.modules.clip.analyze import analyze, pick_in_main_scene, probe
from promovo.modules.clip.render import ClipOverlay, ClipSpec, ClipText, ProductCard, caption_chunks, \
    caption_timing, timeline
from promovo.modules.clip.service import AIClip, make_reel, plan_texts, template_script
from promovo.modules.flyer.service import ingest_flyer
from promovo.modules.video.render import ffmpeg_path
from promovo.money import format_eur

from conftest import TODAY, FakeLLM, make_store, register, upload

FF = ffmpeg_path()


def _ff(*args: str) -> None:
    subprocess.run([FF, "-y", "-v", "error", *args], check=True)


@pytest.fixture(scope="module")
def footage(tmp_path_factory) -> Path:
    """Video "da telefono" di prova: 1,6 s mosso e grigio (pavimento), poi due inquadrature nitide."""
    d = tmp_path_factory.mktemp("footage")
    _ff("-f", "lavfi", "-i", "color=c=gray:s=360x640:d=1.6:r=30", "-vf", "noise=alls=8:allf=t,boxblur=8",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(d / "a.mp4"))
    _ff("-f", "lavfi", "-i", "testsrc2=s=360x640:d=3.4:r=30", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(d / "b.mp4"))
    _ff("-f", "lavfi", "-i", "smptehdbars=s=360x640:d=3:r=30", "-vf", "hue=h=40",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(d / "c.mp4"))
    out = d / "banco.mp4"
    _ff("-i", str(d / "a.mp4"), "-i", str(d / "b.mp4"), "-i", str(d / "c.mp4"),
        "-f", "lavfi", "-t", "8", "-i", "anoisesrc=color=pink:amplitude=0.05:r=48000",
        "-filter_complex", "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]", "-map", "[v]", "-map", "3:a",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(out))
    return out


@pytest.fixture(scope="module")
def landscape_rotated(tmp_path_factory) -> Path:
    """Video girato col telefono in verticale ma salvato orizzontale con l'indicazione di rotazione."""
    d = tmp_path_factory.mktemp("rot")
    raw = d / "raw.mp4"
    _ff("-f", "lavfi", "-i", "testsrc2=s=640x360:d=3:r=30", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(raw))
    out = d / "rot.mp4"
    _ff("-display_rotation", "90", "-i", str(raw), "-c", "copy", str(out))
    return out


def _voice_wav(seconds: float = 4.0) -> bytes:
    """Una "voce" di prova: tono modulato con pause, abbastanza per passare i controlli di silenzio."""
    sr = 48000
    t = np.arange(int(sr * seconds)) / sr
    sig = 0.3 * np.sin(2 * np.pi * 180 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 3 * t))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((sig * 32767).astype("<i2").tobytes())
    return buf.getvalue()


@pytest.fixture
def flyer(session, store, sample_pdf, tmp_settings):
    return ingest_flyer(session, store, sample_pdf, tmp_settings, None, today=TODAY)


# ------------------------------------------------------------------ analisi

def test_probe_reads_rotation(landscape_rotated):
    info = probe(landscape_rotated)
    assert (info.width, info.height) == (360, 640)          # come lo si vede sul telefono
    assert info.rotation in (90, 270) and info.vertical


def test_analysis_skips_blurry_start_and_finds_the_cut(footage):
    a = analyze(footage)
    assert a.info.vertical and a.info.has_audio
    assert all(s.start >= 1.5 for s in a.segments)            # il tratto mosso e grigio è scartato
    assert any(abs(c - 5.0) < 0.5 for c in a.cuts)             # cambio d'inquadratura a 5 s
    for s in a.segments:                                      # nessun tratto a cavallo del cambio
        assert not (s.start + 0.2 < 5.0 < s.end - 0.2)
    segs, trimmed = pick_in_main_scene(a.times, a.score, a.cuts, 11.0)
    assert trimmed and len({s.start < 5.0 for s in segs}) == 1  # prodotto scelto a mano: una sola inquadratura


def test_too_short_video_is_refused(tmp_path):
    p = tmp_path / "corto.mp4"
    _ff("-f", "lavfi", "-i", "testsrc2=s=320x240:d=1:r=30", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(p))
    from promovo.modules.clip.analyze import ClipError
    with pytest.raises(ClipError, match="troppo corto"):
        analyze(p)


# ------------------------------------------------------------------ testi

def test_caption_chunks_and_timing():
    chunks = caption_chunks("Spigole, alici e vongole: le trovi al nostro banco del pesce. Ti aspettiamo in negozio.")
    assert all(len(c) <= 34 for c in chunks)
    assert chunks[-1] == "Ti aspettiamo in negozio."              # le frasi non si mescolano
    timed = caption_timing(chunks, 1.0, 9.0)
    assert timed[0][1] == 1.0 and abs(timed[-1][2] - 9.0) < 1e-6
    assert all(b > a for _, a, b in timed)


def test_spoken_text():
    s = voicemod.to_spoken("Spigola 300/700 g a € 12,99 al kg, mozzarella 4 x 175 g a 3,99 €, birra 66 cl a € 0,99")
    assert "12 euro e 99 al chilo" in s and "3 euro e 99" in s and "99 centesimi" in s
    assert "grammi" in s and "centilitri" in s and "€" not in s


def test_template_script_uses_only_true_facts(store, flyer):
    o = flyer.offers[0]
    hook, script = template_script(store, [o], flyer, note="arrivate stamattina da Anzio")
    assert "Arrivate stamattina da Anzio." in script                     # la nota del negoziante, parola per parola
    assert o.name.lower()[:6] in script.lower() and "22 novembre" in script
    hook2, script2 = template_script(store, [o], flyer)
    assert "stamattina" not in script2


def _plan(store, flyer, footage, llm, chosen=None, note=""):
    return plan_texts(store, flyer, analyze(footage), footage, llm, chosen, note)


def test_ai_recognises_products_per_segment(store, flyer, footage, fake_llm):
    offers = flyer.offers
    fake_llm.on_parse("AIClip", lambda c: AIClip(
        fotogrammi=[{"numero": 1, "visto": "x", "offerta": 2, "frase": "Primo prodotto"},
                    {"numero": 2, "visto": "y", "offerta": 99, "frase": "Non so cosa sia"}],
        titolo="Dal nostro banco",
        voce=f"Da noi {offers[1].name} a {format_eur(offers[1].price_cents)}."))
    plan = _plan(store, flyer, footage, fake_llm)
    assert plan.offers[0] is offers[1]                       # numero 2 dell'elenco
    assert all(o is None for o in plan.offers[1:])            # numero inesistente: nessun prezzo
    assert plan.cards[0].price_cents == offers[1].price_cents
    assert plan.source == "ai" and plan.hook == "Dal nostro banco"


def test_ai_text_with_invented_price_or_claim_is_replaced(store, flyer, footage, fake_llm):
    fake_llm.on_parse("AIClip", lambda c: AIClip(fotogrammi=[{"numero": 1, "visto": "x", "offerta": 1}],
                                                 titolo="Pesce", voce="Tutto a € 0,10 solo oggi."))
    plan = _plan(store, flyer, footage, fake_llm)
    assert plan.source == "template" and "0,10" not in plan.script
    assert any("prezzo" in w for w in plan.warnings)
    fake_llm.on_parse("AIClip", lambda c: AIClip(fotogrammi=[{"numero": 1, "visto": "x", "offerta": 1}],
                                                 titolo="Pesce", voce="Pescato stamattina, freschissimo."))
    plan = _plan(store, flyer, footage, fake_llm)
    assert plan.source == "template" and "stamattina" not in plan.script.lower()
    plan = _plan(store, flyer, footage, fake_llm, note="pescato stamattina ad Anzio")   # se lo dice il negoziante, sì
    assert plan.source == "ai"


def test_without_ai_and_without_product_no_price_is_shown(store, flyer, footage):
    plan = _plan(store, flyer, footage, None)
    assert all(c is None for c in plan.cards)
    assert any("Nessun prodotto" in w for w in plan.warnings)


def test_overlay_declares_ai_voice(footage):
    a = analyze(footage)
    text = ClipText(hook="Prova", cards=[ProductCard("Spigola", 1299)] * len(a.segments))
    spec = ClipSpec(source=footage, info=a.info, segments=a.segments, store_name="Negozio", text=text,
                    voice_is_ai=True)
    ov = ClipOverlay(spec, 8.0, 0.5, 5.0)
    assert ov.ai_label is not None
    assert len(ov.cards) == 1                                 # stesso prodotto nei tratti vicini: un solo cartellino
    frame = ov.frame(3.0)
    assert frame.size == (1080, 1920) and frame.getextrema()[3][1] > 0
    spans = timeline(a.segments, 8.0)
    assert spans[0][0] == 0 and spans[-1][1] == 8.0


# ------------------------------------------------------------------ montaggio completo

def _streams(path: Path) -> str:
    return subprocess.run([FF, "-hide_banner", "-i", str(path)], capture_output=True, text=True).stderr


def test_make_reel_with_chosen_product(session, store, flyer, footage, tmp_settings, tmp_path):
    src = tmp_path / "v.mp4"
    src.write_bytes(footage.read_bytes())
    o = flyer.offers[0]
    piece = make_reel(session, store, tmp_settings, None, src, offer_id=o.id, today=TODAY)
    out = Path(piece.file_path)
    assert out.exists() and Path(piece.meta["poster"]).exists()
    info = _streams(out)
    assert "1080x1920" in info and "Audio:" in info
    assert 8.0 < piece.meta["duration"] < 12.0                 # minimo 6 s di video + 2,8 s di chiusura
    assert set(piece.meta["offers"]) == {o.id} and piece.flyer_id == flyer.id
    assert piece.meta["warnings"]                              # ha avvisato di aver tenuto una sola inquadratura
    assert o.name in piece.body and "€" in piece.body          # didascalia pronta da incollare
    assert piece.approved is False


def test_make_reel_with_recorded_voice(session, store, flyer, footage, tmp_settings, tmp_path):
    src = tmp_path / "v.mp4"
    src.write_bytes(footage.read_bytes())
    voice = tmp_path / "voce.wav"
    voice.write_bytes(_voice_wav(9.0))
    piece = make_reel(session, store, tmp_settings, None, src, offer_id=flyer.offers[1].id,
                      voice_mode="recorded", voice_file=voice, today=TODAY,
                      spoken_script="Buongiorno! Oggi vi consiglio questo, a un prezzo onesto.")
    assert piece.meta["voice"] == "recorded" and piece.meta["ai_voice"] is False
    assert piece.meta["script"] == "Buongiorno! Oggi vi consiglio questo, a un prezzo onesto."   # sottotitoli = parole dette
    assert piece.meta["duration"] >= 9.0 + 1.0 + 2.8 - 0.3      # dura quanto serve per dire tutto il testo


def test_ai_voice_needs_consent_and_key(session, store, flyer, footage, tmp_settings, tmp_path, monkeypatch):
    from promovo.modules.clip.service import ClipFailed
    src = tmp_path / "v.mp4"
    src.write_bytes(footage.read_bytes())
    with pytest.raises(ClipFailed, match="consenso"):
        make_reel(session, store, tmp_settings, None, src, offer_id=flyer.offers[0].id, voice_mode="ai", today=TODAY)
    store.voice_id, store.voice_consent_at = "voce123", TODAY
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    with pytest.raises(ClipFailed, match="chiave"):
        make_reel(session, store, tmp_settings, None, src, offer_id=flyer.offers[0].id, voice_mode="ai", today=TODAY)


def test_tts_call_and_errors(tmp_path):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"], seen["key"] = str(request.url), request.headers.get("xi-api-key")
        if "bad" in str(request.url):
            return httpx.Response(401, json={"detail": {"message": "invalid"}})
        return httpx.Response(200, content=b"ID3fakeaudio")
    client = httpx.Client(transport=httpx.MockTransport(handler))
    out = voicemod.synthesize("Ciao", "voce123", tmp_path / "a.mp3", "k-1", client=client)
    assert out.read_bytes().startswith(b"ID3") and "/text-to-speech/voce123" in seen["url"] and seen["key"] == "k-1"
    with pytest.raises(voicemod.VoiceError, match="non valida"):
        voicemod.synthesize("Ciao", "bad", tmp_path / "b.mp3", "k-1", client=client)


# ------------------------------------------------------------------ API

@pytest.fixture
def client(tmp_settings):
    app = create_app(tmp_settings, llm=FakeLLM(), db=Database("sqlite://"))
    with TestClient(app) as c:
        yield c


def test_api_clip_flow(client, footage, sample_pdf):
    h = register(client)
    st = make_store(client, h)
    flyer = upload(client, h, st["id"], sample_pdf)
    offer = flyer["offers"][0]
    r = client.get(f"/api/stores/{st['id']}/clips/script", params={"offer_id": offer["id"], "note": ""}, headers=h)
    assert r.status_code == 200 and offer["price"] in r.json()["script"]
    r = client.post(f"/api/stores/{st['id']}/clips", headers=h, data={"offer_id": str(offer["id"]), "voice_mode": "none"},
                    files={"video": ("banco.mp4", footage.read_bytes(), "video/mp4")})
    assert r.status_code == 202, r.text
    job = client.get(f"/api/jobs/{r.json()['id']}", headers=h).json()
    assert job["status"] == "done", job
    clips = client.get(f"/api/stores/{st['id']}/clips", headers=h).json()
    assert len(clips) == 1 and clips[0]["file_url"] and clips[0]["poster_url"]
    assert client.get(clips[0]["file_url"], headers=h).headers["content-type"] == "video/mp4"
    # compare anche tra i materiali del volantino (passo 3) e nel pacchetto ZIP
    assert any(c["id"] == clips[0]["id"] for c in client.get(f"/api/flyers/{flyer['id']}/content", headers=h).json())
    assert client.delete(f"/api/content/{clips[0]['id']}", headers=h).status_code == 204
    assert client.get(f"/api/stores/{st['id']}/clips", headers=h).json() == []


def test_api_clip_rejects_bad_input(client):
    h = register(client)
    st = make_store(client, h)
    r = client.post(f"/api/stores/{st['id']}/clips", headers=h, data={"voice_mode": "none"},
                    files={"video": ("foto.jpg", b"xxx", "image/jpeg")})
    assert r.status_code == 400 and "non supportato" in r.json()["detail"]
    r = client.post(f"/api/stores/{st['id']}/clips", headers=h, data={"voice_mode": "ai"},
                    files={"video": ("v.mp4", b"xxx", "video/mp4")})
    assert r.status_code == 409 and "consenso" in r.json()["detail"]
    r = client.post(f"/api/stores/{st['id']}/clips", headers=h, data={"voice_mode": "recorded"},
                    files={"video": ("v.mp4", b"xxx", "video/mp4")})
    assert r.status_code == 400 and "registrazione" in r.json()["detail"]
    # un video illeggibile fa fallire il lavoro con un messaggio chiaro, senza bloccare nulla
    r = client.post(f"/api/stores/{st['id']}/clips", headers=h, data={"voice_mode": "none"},
                    files={"video": ("v.mp4", b"non sono un video", "video/mp4")})
    job = client.get(f"/api/jobs/{r.json()['id']}", headers=h).json()
    assert job["status"] == "failed" and "video" in job["error"].lower()


def test_api_voice_consent_and_clone(client, monkeypatch):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.method == "POST":
            return httpx.Response(200, json={"voice_id": "v-777"})
        return httpx.Response(200, json={})
    client.app.state.promovo.voice_client = httpx.Client(transport=httpx.MockTransport(handler))
    h = register(client)
    st = make_store(client, h)
    sample = {"sample": ("voce.wav", _voice_wav(35.0), "audio/wav")}
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    r = client.post(f"/api/stores/{st['id']}/voice", headers=h, data={"consent_name": "Mario Rossi", "consent": "true"},
                    files=sample)
    assert r.status_code == 409                                   # senza chiave
    monkeypatch.setenv("ELEVENLABS_API_KEY", "k-test")
    r = client.post(f"/api/stores/{st['id']}/voice", headers=h, data={"consent_name": "Mario Rossi"}, files=sample)
    assert r.status_code == 400 and "consenso" in r.json()["detail"]
    short = {"sample": ("voce.wav", _voice_wav(5.0), "audio/wav")}
    r = client.post(f"/api/stores/{st['id']}/voice", headers=h, data={"consent_name": "Mario Rossi", "consent": "true"},
                    files=short)
    assert r.status_code == 400 and "almeno 30" in r.json()["detail"]
    r = client.post(f"/api/stores/{st['id']}/voice", headers=h, data={"consent_name": "Mario Rossi", "consent": "true"},
                    files=sample)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["voice_ready"] and body["voice_consent_name"] == "Mario Rossi" and body["voice_consent_at"]
    assert ("POST", "/v1/voices/add") in calls
    r = client.delete(f"/api/stores/{st['id']}/voice", headers=h)
    assert r.status_code == 200 and not r.json()["voice_ready"]
    assert ("DELETE", "/v1/voices/v-777") in calls
