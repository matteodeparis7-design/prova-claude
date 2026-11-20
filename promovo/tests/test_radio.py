"""Radio del punto vendita: annunci dai dati del negozio, musica che si abbassa sotto la voce, MP3 in loop."""
from __future__ import annotations

import math
import struct
import wave

from fastapi.testclient import TestClient

from promovo.api import create_app
from promovo.db import Database
from promovo.modules import accessible, radio
from promovo.modules.video.render import probe_duration

from conftest import FakeLLM, make_store, register, upload


def _fake_speak(store, text, engine, out_wav):
    n = int(44100 * min(6, max(1.5, len(text) / 30)))
    with wave.open(str(out_wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"".join(struct.pack("<h", int(9000 * math.sin(i / 9))) for i in range(n)))
    return out_wav


def test_mix_ducks_music_under_voice():
    import numpy as np
    sr = 44100
    v = (0.5 * np.sin(np.arange(sr * 3) * 2 * np.pi * 300 / sr)).astype(np.float32)
    m = radio.mix([v], 20.0)
    assert m.shape == (20 * sr, 2) and float(np.abs(m).max()) <= 0.91


def test_api(tmp_settings, live_pdf, monkeypatch):
    app = create_app(tmp_settings, llm=FakeLLM(), db=Database("sqlite://"))
    with TestClient(app) as c:
        h = register(c)
        s = make_store(c, h)
        upload(c, h, s["id"], live_pdf)
        c.post(f"/api/stores/{s['id']}/notices", headers=h,
               json={"kind": "chiusura", "title": "Chiusura per inventario", "date_from": __import__("datetime").date.today().isoformat(),
                     "closed": True})
        info = c.get(f"/api/stores/{s['id']}/radio", headers=h).json()
        a = info["announcements"]
        assert a[0].startswith("Benvenuti da Superstore Colleferro") and "voce sintetica" in a[0]
        assert any("in offerta" in x and "euro" in x for x in a)                  # prezzi detti a voce
        assert any("Chiusura per inventario" in x for x in a)
        assert "chiude tra 15 minuti" in info["closing"] and info["minutes"] == [3, 5, 10]
        monkeypatch.setattr(accessible, "windows_voice", lambda: None)
        r = c.post(f"/api/stores/{s['id']}/radio", headers=h, json={"engine": "windows", "minutes": 3})
        assert r.status_code == 400 and "voce italiana" in r.json()["detail"]
        monkeypatch.setattr(accessible, "speak_wav", _fake_speak)
        r = c.post(f"/api/stores/{s['id']}/radio", headers=h, json={"engine": "windows", "minutes": 3,
                                                                     "announcements": a[:4]})
        assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg"
        out = tmp_settings.data_dir / "prova_radio.mp3"
        out.write_bytes(r.content)
        assert 175 <= probe_duration(out) <= 185                                # 3 minuti, da mandare in loop
        r = c.post(f"/api/stores/{s['id']}/radio", headers=h, json={"engine": "windows", "closing": True})
        assert r.status_code == 200 and len(r.content) > 10000
        assert c.post(f"/api/stores/{s['id']}/radio", headers=h,
                      json={"engine": "windows", "minutes": 7}).status_code == 400
        h2 = register(c, email="altro@test.it", org="Altra")
        assert c.get(f"/api/stores/{s['id']}/radio", headers=h2).status_code == 404
