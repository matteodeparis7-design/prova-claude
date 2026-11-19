"""Copia di sicurezza, ripristino e pacchetto per l'assistenza.

- Copia di sicurezza: un file ZIP con il database (copiato in modo sicuro anche mentre Promovo lavora) e i
  file dei negozi (volantini, ritagli, grafiche, video, loghi, voci). Restano fuori i modelli degli agenti
  aggiuntivi (si riscaricano) e i file temporanei.
- Ripristino: la copia viene controllata e messa da parte; al riavvio successivo Promovo sposta i dati
  attuali in una cartella «prima del ripristino» (non si perde niente) e rimette quelli della copia,
  aggiornando i percorsi dei file, così la copia funziona anche su un altro computer o in un'altra cartella.
- Pacchetto per l'assistenza: registro degli eventi, versioni e stato degli agenti. Mai le chiavi.
"""
from __future__ import annotations

import io
import json
import logging
import platform
import shutil
import sqlite3
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

log = logging.getLogger("promovo.backup")

MANIFEST = "promovo-backup.json"
PENDING = "ripristino_in_attesa.zip"
SKIP_DIRS = {"models", "tmp", "__pycache__"}
SKIP_FILES = {PENDING, "registro.txt", "chiavi.json"}


class BackupError(ValueError):
    pass


def db_path(database_url: str) -> Path | None:
    if database_url.startswith("sqlite:///"):
        return Path(database_url[len("sqlite:///"):])
    return None


def _copy_db(src: Path, dst: Path) -> None:
    """Copia coerente del database anche con Promovo acceso (API di backup di SQLite)."""
    with sqlite3.connect(str(src)) as a, sqlite3.connect(str(dst)) as b:
        a.backup(b)


def make_backup(data_dir: Path, database_url: str, out: Path, include_videos: bool = True,
                version: str = "") -> Path:
    data_dir = Path(data_dir)
    db = db_path(database_url)
    if db is None or not db.exists():
        raise BackupError("La copia di sicurezza funziona con il database di Promovo sul computer.")
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "promovo.db"
        _copy_db(db, copy)
        with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as z:
            z.writestr(MANIFEST, json.dumps({
                "app": "Promovo", "version": version, "created": datetime.now().isoformat(timespec="seconds"),
                "data_dir": str(data_dir.resolve()), "videos": include_videos}, ensure_ascii=False, indent=1))
            z.write(copy, "promovo.db")
            for p in sorted(data_dir.rglob("*")):
                rel = p.relative_to(data_dir)
                if p.is_dir() or rel.parts[0] in SKIP_DIRS or p.name in SKIP_FILES or p.resolve() == db.resolve():
                    continue
                if p.suffix.lower() in (".part", ".tmp", ".db-journal", ".db-wal", ".db-shm"):
                    continue
                if not include_videos and p.suffix.lower() in (".mp4", ".mov", ".webm"):
                    continue
                z.write(p, "dati/" + rel.as_posix())
    return out


def check_backup(data: bytes) -> dict:
    """Controlla che il file sia una copia di Promovo integra; restituisce le sue informazioni."""
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise BackupError("Il file non è una copia di sicurezza di Promovo (ZIP non valido).") from exc
    names = set(z.namelist())
    if MANIFEST not in names or "promovo.db" not in names:
        raise BackupError("Il file non è una copia di sicurezza di Promovo.")
    for n in names:                                   # niente percorsi che escono dalla cartella dei dati
        if n.startswith(("/", "\\")) or ".." in Path(n).parts or ":" in n:
            raise BackupError("La copia contiene percorsi non validi.")
    bad = z.testzip()
    if bad:
        raise BackupError(f"La copia è danneggiata (file {bad}).")
    info = json.loads(z.read(MANIFEST).decode("utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "c.db"
        p.write_bytes(z.read("promovo.db"))
        try:
            with sqlite3.connect(str(p)) as c:
                stores = c.execute("select count(*) from stores").fetchone()[0]
                flyers = c.execute("select count(*) from flyers").fetchone()[0]
        except sqlite3.DatabaseError as exc:
            raise BackupError("Il database nella copia non è leggibile.") from exc
    return {**info, "stores": stores, "flyers": flyers}


def stage_restore(data: bytes, data_dir: Path) -> dict:
    info = check_backup(data)
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    (Path(data_dir) / PENDING).write_bytes(data)
    return info


def _rewrite_paths(db: Path, old: str, new: str) -> int:
    """Aggiorna nel database i percorsi dei file dalla vecchia cartella dei dati alla nuova."""
    if not old or old == new:
        return 0
    pairs = [(old, new), (old.replace("\\", "\\\\"), new.replace("\\", "\\\\")),     # anche dentro i JSON
             (old.replace("\\", "/"), new.replace("\\", "/"))]
    changed = 0
    with sqlite3.connect(str(db)) as c:
        tables = [r[0] for r in c.execute("select name from sqlite_master where type='table'")]
        for t in tables:
            cols = [r[1] for r in c.execute(f'pragma table_info("{t}")') if (r[2] or "").upper() in
                    ("TEXT", "VARCHAR", "JSON", "") or (r[2] or "").upper().startswith("VARCHAR")]
            for col in cols:
                for a, b in pairs:
                    cur = c.execute(f'update "{t}" set "{col}" = replace("{col}", ?, ?) where "{col}" like ?',
                                    (a, b, f"%{a}%"))
                    changed += cur.rowcount
        c.commit()
    return changed


def apply_pending_restore(data_dir: Path, database_url: str) -> str | None:
    """Da chiamare all'avvio, prima di aprire il database. Restituisce un messaggio se ha ripristinato."""
    data_dir = Path(data_dir)
    pending = data_dir / PENDING
    db = db_path(database_url)
    if not pending.exists() or db is None:
        return None
    try:
        data = pending.read_bytes()
        info = check_backup(data)
    except Exception as exc:
        log.error("Copia di sicurezza in attesa non valida: %s", exc)
        pending.rename(pending.with_suffix(".non_valida.zip"))
        return None
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    keep = data_dir / f"prima del ripristino {stamp}"
    keep.mkdir(parents=True, exist_ok=True)
    for p in list(data_dir.iterdir()):                # i dati attuali si mettono da parte, non si cancellano
        if p == keep or p.name == PENDING or p.name.startswith("prima del ripristino") or p.name in ("models",):
            continue
        shutil.move(str(p), str(keep / p.name))
    if db.exists():
        shutil.move(str(db), str(keep / db.name))
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for n in z.namelist():
            if n.startswith("dati/") and not n.endswith("/"):
                dest = data_dir / n[len("dati/"):]
                dest.parent.mkdir(parents=True, exist_ok=True)
                with z.open(n) as src, dest.open("wb") as out:
                    shutil.copyfileobj(src, out)
        db.parent.mkdir(parents=True, exist_ok=True)
        with z.open("promovo.db") as src, db.open("wb") as out:
            shutil.copyfileobj(src, out)
    _rewrite_paths(db, info.get("data_dir", ""), str(data_dir.resolve()))
    pending.unlink(missing_ok=True)
    msg = (f"Ripristinata la copia del {info.get('created', '?')} ({info.get('stores', 0)} negozi, "
           f"{info.get('flyers', 0)} volantini). I dati di prima sono in «{keep.name}».")
    log.info(msg)
    return msg


def diagnostics(data_dir: Path, settings_info: dict, extras_status: list, jobs: list[dict], version: str) -> bytes:
    """Pacchetto per l'assistenza: niente chiavi, niente foto o video dei negozi."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("informazioni.json", json.dumps({
            "promovo": version, "python": sys.version.split()[0], "sistema": platform.platform(),
            "creato": datetime.now().isoformat(timespec="seconds"), "impostazioni": settings_info,
            "agenti_aggiuntivi": extras_status, "ultimi_lavori": jobs}, ensure_ascii=False, indent=1, default=str))
        logf = Path(data_dir) / "registro.txt"
        if logf.exists():
            raw = logf.read_bytes()[-3_000_000:]
            z.writestr("registro.txt", raw)
    return buf.getvalue()
