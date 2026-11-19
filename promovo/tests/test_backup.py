"""Copia di sicurezza, ripristino (anche in un'altra cartella) e pacchetto per l'assistenza."""
from __future__ import annotations

import dataclasses
import io
import json
import sqlite3
import zipfile

import pytest
from fastapi.testclient import TestClient

from promovo import backup
from promovo.api import create_app

from conftest import FakeLLM, make_store, register, upload


@pytest.fixture
def file_app(tmp_path, tmp_settings):
    a = tmp_path / "A"
    st = dataclasses.replace(tmp_settings, data_dir=a / "dati", database_url=f"sqlite:///{a}/promovo.db")
    a.mkdir()
    return st


def test_backup_and_restore_elsewhere(file_app, tmp_path, live_pdf):
    app = create_app(file_app, llm=FakeLLM())
    with TestClient(app) as c:
        h = register(c)
        s = make_store(c, h)
        f = upload(c, h, s["id"], live_pdf)
        (file_app.data_dir / "chiavi.json").write_text('{"ai": "sk-ant-segreta"}')
        r = c.get("/api/backup", headers=h)
        assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
        z = zipfile.ZipFile(io.BytesIO(r.content))
        names = set(z.namelist())
        assert {"promovo-backup.json", "promovo.db"} <= names
        assert any(n.startswith("dati/flyers/") for n in names) and any(n.startswith("dati/crops/") for n in names)
        assert not any("chiavi" in n for n in names)                    # le chiavi non finiscono mai nella copia
        info = backup.check_backup(r.content)
        assert info["stores"] == 1 and info["flyers"] == 1
        # pacchetto per l'assistenza: niente chiavi
        d = c.get("/api/diagnostics", headers=h)
        dz = zipfile.ZipFile(io.BytesIO(d.content))
        assert "informazioni.json" in dz.namelist() and b"sk-ant" not in d.content
        assert json.loads(dz.read("informazioni.json"))["promovo"]
    # ripristino su «un altro computer»: altra cartella, altri percorsi
    b = tmp_path / "B"
    data_b, url_b = b / "dati", f"sqlite:///{b}/promovo.db"
    info = backup.stage_restore(r.content, data_b)
    assert info["flyers"] == 1 and (data_b / backup.PENDING).exists()
    msg = backup.apply_pending_restore(data_b, url_b)
    assert msg and "1 negozi" in msg
    with sqlite3.connect(str(b / "promovo.db")) as conn:
        pdf = conn.execute("select pdf_path from flyers").fetchone()[0]
        crop = conn.execute("select crop_path from offers limit 1").fetchone()[0]
    assert pdf.startswith(str(data_b.resolve())) and (data_b / "flyers").exists()
    from pathlib import Path
    assert Path(pdf).exists() and Path(crop).exists()
    assert not (data_b / backup.PENDING).exists()


def test_restore_keeps_current_data_aside(file_app, live_pdf):
    app = create_app(file_app, llm=FakeLLM())
    with TestClient(app) as c:
        h = register(c)
        make_store(c, h)
        bk = c.get("/api/backup", headers=h).content
        r = c.post("/api/restore", headers=h, files={"file": ("copia.zip", bk, "application/zip")})
        assert r.status_code == 200 and "riaprilo" in r.json()["message"]
        bad = c.post("/api/restore", headers=h, files={"file": ("x.zip", b"non sono uno zip", "application/zip")})
        assert bad.status_code == 400
    # «riavvio»: il ripristino si completa e i dati di prima restano in una cartella a parte
    app2 = create_app(file_app, llm=FakeLLM())
    with TestClient(app2) as c:
        info = c.get("/api/system", headers=register(c, email="altro@test.it", org="Altro")).json()
        assert info["restored"] and "prima del ripristino" in info["restored"]
    kept = [p for p in file_app.data_dir.iterdir() if p.name.startswith("prima del ripristino")]
    assert kept and (kept[0] / "promovo.db").exists()


def test_backup_refuses_dangerous_paths():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("promovo-backup.json", "{}")
        z.writestr("promovo.db", b"")
        z.writestr("dati/../../fuori.txt", "x")
    with pytest.raises(backup.BackupError, match="percorsi"):
        backup.check_backup(buf.getvalue())


def test_update_check(tmp_settings, monkeypatch):
    import promovo.version as v
    app = create_app(tmp_settings, llm=FakeLLM())
    with TestClient(app) as c:
        h = register(c)
        assert c.get("/api/update", headers=h).json()["available"] is False      # dai sorgenti: niente avvisi
        monkeypatch.setattr(v, "build", lambda: {"commit": "aaa", "date": "2026-11-19T10:00:00Z"})
        app.state.promovo.update_fetch = lambda: {"target_commitish": "bbb", "published_at": "2026-11-20T09:00:00Z"}
        r = c.get("/api/update", headers=h).json()
        assert r["available"] is True and r["url"].startswith("https://github.com/")
