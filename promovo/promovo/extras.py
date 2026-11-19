"""Agenti aggiuntivi: modelli open source che lavorano sul computer, senza mandare dati fuori.

- «cutout»: BiRefNet lite (licenza MIT) scontorna i prodotti delle foto del volantino.
- «subtitles»: Whisper small (OpenAI, licenza MIT; versione CTranslate2 di SYSTRAN, MIT) trascrive la voce
  dei Reel «Dal banco» per sottotitoli a tempo di parola.

Sicurezza: ogni file si scarica da un indirizzo fisso, a una versione fissa (commit), e si controlla la sua
impronta SHA-256 prima di usarlo. Se l'impronta non corrisponde il file viene cancellato.
Un modello può essere già incluso nell'installazione (cartella assets/models) oppure scaricato con un clic
dalle Impostazioni (cartella «models» dentro i dati di Promovo).
"""
from __future__ import annotations

import hashlib
import logging
import threading
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

log = logging.getLogger("promovo.extras")

BUNDLED = Path(__file__).resolve().parent / "assets" / "models"


@dataclass(frozen=True)
class ModelFile:
    url: str
    name: str
    sha256: str
    size: int


@dataclass(frozen=True)
class Extra:
    key: str
    title: str
    what: str
    license: str
    folder: str
    files: tuple[ModelFile, ...]

    @property
    def size(self) -> int:
        return sum(f.size for f in self.files)


_HF = "https://huggingface.co"
_WHISPER_REV = "536b0662742c02347bc0e980a01041f333bce120"
_BIREF_REV = "de15b22ba131738a16dff04aab8bdf8dc32e3ac1"

EXTRAS: dict[str, Extra] = {
    "cutout": Extra(
        key="cutout", title="Scontorno dei prodotti",
        what="Ritaglia il prodotto dalla foto del volantino, senza sfondo e senza scritte, per grafiche e video più puliti.",
        license="BiRefNet lite, licenza MIT", folder="birefnet-lite",
        files=(ModelFile(f"{_HF}/onnx-community/BiRefNet_lite-ONNX/resolve/{_BIREF_REV}/onnx/model.onnx",
                         "model.onnx", "5600024376f572a557870a5eb0afb1e5961636bef4e1e22132025467d0f03333",
                         224005088),)),
    "subtitles": Extra(
        key="subtitles", title="Sottotitoli automatici",
        what="Ascolta la voce dei Reel «Dal banco» e mette i sottotitoli parola per parola, sincronizzati.",
        license="Whisper small (OpenAI) in versione CTranslate2 (SYSTRAN), licenza MIT", folder="whisper-small",
        files=(
            ModelFile(f"{_HF}/Systran/faster-whisper-small/resolve/{_WHISPER_REV}/model.bin", "model.bin",
                      "3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671", 483546902),
            ModelFile(f"{_HF}/Systran/faster-whisper-small/resolve/{_WHISPER_REV}/config.json", "config.json",
                      "b55496ac7940a7ae47d2c01eab40edfd8701feec1229d9cce3b40014383fb828", 2370),
            ModelFile(f"{_HF}/Systran/faster-whisper-small/resolve/{_WHISPER_REV}/tokenizer.json", "tokenizer.json",
                      "fb7b63191e9bb045082c79fd742a3106a12c99513ab30df4a0d47fa6cb6fd0ab", 2203239),
            ModelFile(f"{_HF}/Systran/faster-whisper-small/resolve/{_WHISPER_REV}/vocabulary.txt", "vocabulary.txt",
                      "34ce3fe1c5041027b3f8d42912270993f986dbc4bb34cf27f951e34a1e453913", 459861),
        )),
}

# I dati di Promovo (impostati all'avvio dall'applicazione): lì finiscono i modelli scaricati.
_data_dir: list[Path] = []
_progress: dict[str, dict] = {}
_lock = threading.Lock()


def set_data_dir(path: Path) -> None:
    _data_dir[:] = [Path(path)]


def _candidates(extra: Extra) -> list[Path]:
    out = [BUNDLED / extra.folder]
    if _data_dir:
        out.append(_data_dir[0] / "models" / extra.folder)
    return out


def _complete(folder: Path, extra: Extra) -> bool:
    return all((folder / f.name).is_file() and (folder / f.name).stat().st_size == f.size for f in extra.files)


def path(key: str) -> Path | None:
    """La cartella del modello se è pronto (incluso o scaricato), altrimenti None."""
    extra = EXTRAS[key]
    for folder in _candidates(extra):
        if _complete(folder, extra):
            return folder
    return None


def status() -> list[dict]:
    out = []
    for e in EXTRAS.values():
        p = path(e.key)
        prog = dict(_progress.get(e.key) or {})
        out.append({"key": e.key, "title": e.title, "what": e.what, "license": e.license,
                    "size_mb": round(e.size / 1_000_000), "ready": p is not None,
                    "bundled": p is not None and p.parent == BUNDLED,
                    "downloading": prog.get("state") == "running", "progress": prog.get("done", 0),
                    "error": prog.get("error", "")})
    return out


def _sha256(file: Path) -> str:
    h = hashlib.sha256()
    with file.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(key: str, opener: Callable | None = None) -> Path:
    """Scarica e verifica i file del modello (bloccante: va chiamata in un lavoro in sottofondo)."""
    extra = EXTRAS[key]
    if not _data_dir:
        raise RuntimeError("Cartella dei dati non impostata.")
    folder = _data_dir[0] / "models" / extra.folder
    folder.mkdir(parents=True, exist_ok=True)
    opener = opener or (lambda url: urllib.request.urlopen(  # noqa: S310 (indirizzi fissi, solo https)
        urllib.request.Request(url, headers={"User-Agent": "Promovo/1.0"}), timeout=60))
    total, done = extra.size, 0
    with _lock:
        _progress[key] = {"state": "running", "done": 0}
    try:
        for f in extra.files:
            dest = folder / f.name
            if dest.is_file() and dest.stat().st_size == f.size and _sha256(dest) == f.sha256:
                done += f.size
                continue
            part = dest.with_suffix(dest.suffix + ".part")
            h = hashlib.sha256()
            with opener(f.url) as r, part.open("wb") as out:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    out.write(chunk)
                    h.update(chunk)
                    done += len(chunk)
                    _progress[key]["done"] = min(99, int(done * 100 / total))
            if h.hexdigest() != f.sha256:
                part.unlink(missing_ok=True)
                raise RuntimeError(f"Il file {f.name} non corrisponde all'originale: scaricamento annullato.")
            part.replace(dest)
        _progress[key] = {"state": "done", "done": 100}
        return folder
    except Exception as exc:
        _progress[key] = {"state": "failed", "done": 0, "error": str(exc)[:200]}
        raise


def remove(key: str) -> None:
    """Toglie un modello scaricato (quelli inclusi nell'installazione restano)."""
    if not _data_dir:
        return
    folder = _data_dir[0] / "models" / EXTRAS[key].folder
    if folder.is_dir():
        for f in folder.iterdir():
            f.unlink(missing_ok=True)
        folder.rmdir()
    _progress.pop(key, None)
