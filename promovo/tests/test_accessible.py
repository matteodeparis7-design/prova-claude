"""Volantino accessibile: da ascoltare (voce sul computer) e a caratteri grandi."""
from __future__ import annotations

import math
import struct
import wave

import pymupdf
from fastapi.testclient import TestClient

from promovo.api import create_app
from promovo.db import Database
from promovo.modules import accessible
from promovo.modules.flyer.service import ingest_flyer

from conftest import TODAY, FakeLLM, make_store, register, upload


def _fake_wav(text, out_wav, voice):
    with wave.open(str(out_wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(i / 8))) for i in range(16000 * 2)))


def test_script_is_spoken_and_true(session, store, sample_pdf, tmp_settings):
    f = ingest_flyer(session, store, sample_pdf, tmp_settings, None, today=TODAY)
    t = accessible.script(store, f)
    assert t.startswith(f"Buongiorno da {store.name}") and "voce sintetica" in t
    assert "venerdì 13 novembre" in t and "domenica 22 novembre" in t
    assert "0 euro e 79" not in t and "79 centesimi" in t          # i prezzi si leggono come si dicono
    assert "500 grammi" in t and "€" not in t and "%" not in t
    assert "E altre 2 offerte" in t                                  # 12 offerte, se ne leggono 10
    assert 30 <= accessible.seconds(t) <= 120
    for w in ("buonissim", "fresc", "delizios", "qualità"):
        assert w not in t.lower()


def test_large_print_pdf(session, store, sample_pdf, tmp_settings, tmp_path):
    f = ingest_flyer(session, store, sample_pdf, tmp_settings, None, today=TODAY)
    pdf = accessible.large_print_pdf(store, f, tmp_path / "g.pdf")
    doc = pymupdf.open(pdf)
    assert doc.page_count == 3 and round(doc[0].rect.width) == 595      # 12 offerte, 5 per pagina, A4


def test_api(tmp_settings, live_pdf, monkeypatch):
    app = create_app(tmp_settings, llm=FakeLLM(), db=Database("sqlite://"))
    with TestClient(app) as c:
        h = register(c)
        s = make_store(c, h)
        f = upload(c, h, s["id"], live_pdf)
        monkeypatch.setattr(accessible, "windows_voice", lambda: None)
        info = c.get(f"/api/flyers/{f['id']}/audio", headers=h).json()
        assert info["engines"] == [] and info["text"] and info["seconds"] > 10
        r = c.post(f"/api/flyers/{f['id']}/audio", headers=h, json={"engine": "windows"})
        assert r.status_code == 400 and "voce italiana di Windows" in r.json()["detail"]
        # con la voce italiana di Windows (finta nel test): esce un MP3
        monkeypatch.setattr(accessible, "windows_voice", lambda: "Microsoft Elsa Desktop")
        monkeypatch.setattr(accessible, "_windows_wav", _fake_wav)
        info = c.get(f"/api/flyers/{f['id']}/audio", headers=h).json()
        assert info["engines"][0]["key"] == "windows"
        r = c.post(f"/api/flyers/{f['id']}/audio", headers=h, json={"engine": "windows", "text": info["text"]})
        assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg" and len(r.content) > 5000
        assert c.post(f"/api/flyers/{f['id']}/audio", headers=h, json={"engine": "windows", "text": "x"}).status_code == 400
        pdf = c.get(f"/api/flyers/{f['id']}/print/grandi", headers=h)
        assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
        h2 = register(c, email="altro@test.it", org="Altra")
        assert c.get(f"/api/flyers/{f['id']}/audio", headers=h2).status_code == 404


import platform as _platform
import subprocess as _subprocess

import pytest


@pytest.mark.skipif(_platform.system() != "Windows", reason="la voce di Windows c'è solo su Windows")
def test_windows_speech_really_works(tmp_path):
    """Sulla build Windows: la lettura con System.Speech produce davvero un audio (con la prima voce installata)."""
    ps = ("Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer)"
          ".GetInstalledVoices() | Select-Object -First 1 | ForEach-Object { $_.VoiceInfo.Name }")
    voice = _subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True).stdout.strip()
    if not voice:
        pytest.skip("nessuna voce installata su questo computer")
    out = tmp_path / "prova dell'audio.wav"                     # anche con l'apostrofo nel percorso
    accessible._windows_wav("Spaghetti di grano duro, 79 centesimi.", out, voice)
    assert out.stat().st_size > 5000
    mp3 = accessible._to_mp3(out, tmp_path / "prova.mp3")
    assert mp3.stat().st_size > 1000
