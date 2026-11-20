"""Radio del punto vendita: gli annunci del negozio in loop, con musica originale.

Le grandi catene hanno la loro radio in negozio (uno studio del Politecnico di Milano con Carrefour ha misurato
+19,5% di vendite sui prodotti annunciati). Promovo la porta a ogni punto vendita, preparata da sola ogni settimana:
- annunci scritti dai dati del negozio: offerte del volantino (a rotazione), avvisi in corso (orari festivi,
  chiusure), Salvaspreco del giorno, il produttore della settimana, orari e servizi;
- letti con la voce italiana del computer o con la voce del negozio; all'inizio si dice che è una voce sintetica;
- un breve suono prima di ogni annuncio e la musica originale di Promovo che si abbassa quando parla la voce
  (la musica è generata da Promovo: non è un brano di repertorio);
- un file MP3 lungo qualche minuto da mandare in loop, più l'annuncio di chiusura a parte.
"""
from __future__ import annotations

import subprocess
import tempfile
import wave
from datetime import date
from pathlib import Path

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Notice, Rescue, Store
from ..money import format_eur
from .. import voice as voicemod
from . import accessible
from .catalog import active_flyers
from .content.service import featured_offers
from .video.music import SR, chime, compose

MAX_ANNOUNCEMENTS = 12
MINUTES = (3, 5, 10)


class RadioError(RuntimeError):
    pass


# ----------------------------------------------------------------- gli annunci

def _offer_line(o) -> str:
    name = " ".join(x for x in (o.brand, o.name) if x)
    size = f", {o.description}" if o.description else ""
    line = f"{name}{size}, a {format_eur(o.price_cents)}"
    if o.old_price_cents and o.old_price_cents > o.price_cents:
        line += f" invece di {format_eur(o.old_price_cents)}"
    return line


def announcements(session: Session, store: Store, today: date | None = None) -> list[str]:
    """Gli annunci della settimana, dai dati del negozio. Il negozio li può modificare prima di creare l'audio."""
    today = today or date.today()
    out = [f"Benvenuti da {store.name}. Gli annunci sono letti da una voce sintetica."]
    flyers = active_flyers(session, store.id, today)
    if flyers:
        f = flyers[0]
        offers = featured_offers(f, 9)
        until = f" Offerte valide fino al {f.valid_to.day} {_month(f.valid_to.month)}." if f.valid_to else ""
        for i in range(0, len(offers), 3):
            group = offers[i:i + 3]
            lead = "Questa settimana in offerta: " if i == 0 else "Ancora dal volantino: "
            out.append(lead + "; ".join(_offer_line(o) for o in group) + "." + (until if i == 0 else ""))
    for n in session.scalars(select(Notice).where(Notice.store_id == store.id, Notice.date_to >= today)
                             .order_by(Notice.date_from).limit(2)):
        from .notices import when
        what = "il negozio resta chiuso" if n.closed else (f"siamo aperti {n.hours}" if n.hours else "")
        out.append(f"Avviso: {n.title}. {when(n)}{', ' + what if what else ''}." + (f" {n.message}" if n.message else ""))
    rescues = session.scalars(select(Rescue).where(Rescue.store_id == store.id, Rescue.closed_at.is_(None),
                                                   Rescue.day >= today)).all()
    rescues = [r for r in rescues if (r.until or r.day) >= today][:3]
    if rescues:
        out.append("Salvaspreco di oggi, per non sprecare: " + "; ".join(
            f"{r.name}{', ' + r.description if r.description else ''} a {format_eur(r.rescue_price_cents)}"
            for r in rescues) + ". Fino a esaurimento.")
    try:
        from .filiera import of_the_week, store_producers
        p = of_the_week(store_producers(session, store), featured_offers(flyers[0], 20) if flyers else [], today)
        if p is not None and p.km is not None:
            out.append(f"Conosci chi lo produce? {p.what[:1].upper() + p.what[1:]} da {p.name}, a {p.town}, "
                       f"a circa {int(round(p.km))} chilometri da qui.")
    except Exception:          # la filiera è facoltativa
        pass
    if store.opening_hours:
        hrs = "; ".join(f"{k} {v}" for k, v in store.opening_hours.items())
        out.append(f"I nostri orari: {hrs}. Grazie per aver scelto {store.name}.")
    else:
        out.append(f"Grazie per aver scelto {store.name}.")
    return [voicemod.to_spoken(a) for a in out[:MAX_ANNOUNCEMENTS]]


def closing(store: Store, minutes: int = 15) -> str:
    return voicemod.to_spoken(f"Gentili clienti, {store.name} chiude tra {minutes} minuti. Vi invitiamo a "
                              f"raggiungere le casse. Grazie e arrivederci.")


def _month(m: int) -> str:
    return ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre",
            "ottobre", "novembre", "dicembre"][m - 1]


# ----------------------------------------------------------------- il montaggio

def _read_mono(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        if w.getframerate() != SR or w.getsampwidth() != 2:
            raise RadioError("Formato della voce inatteso.")
        data = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768
        if w.getnchannels() == 2:
            data = data.reshape(-1, 2).mean(axis=1)
    return data


def _music_bed(seconds: float, seed: int) -> np.ndarray:
    """Musica di sottofondo lunga `seconds`: un brano di 64 secondi ripetuto con dissolvenze incrociate."""
    piece = compose(64.0, seed=seed)                    # stereo float32
    fade = int(2.0 * SR)
    n = int(seconds * SR)
    out = np.zeros((n, 2), np.float32)
    pos, step = 0, len(piece) - fade
    ramp_in = np.linspace(0, 1, fade, dtype=np.float32)[:, None]
    while pos < n:
        chunk = piece.copy()
        if pos > 0:
            chunk[:fade] *= ramp_in
        end = min(n, pos + len(chunk))
        out[pos:end] += chunk[: end - pos]
        pos += step
    return out


def mix(voices: list[np.ndarray], seconds: float, seed: int = 11) -> np.ndarray:
    """Musica bassa, campanella, annuncio; la musica scende sotto la voce. Gli annunci si distribuiscono nel tempo."""
    n = int(seconds * SR)
    bed = _music_bed(seconds, seed) * 0.32
    gain = np.ones(n, np.float32)
    out = np.zeros((n, 2), np.float32)
    bell = chime(81)
    bell = (bell.mean(axis=1) if bell.ndim == 2 else bell).astype(np.float32)
    if not voices:
        return bed
    slot = n / len(voices)
    for i, v in enumerate(voices):
        start = int(i * slot + min(slot * 0.25, 6 * SR))
        if start + len(v) + int(1.2 * SR) > n:
            start = max(0, n - len(v) - int(1.2 * SR))
        b0 = start
        bl = bell[: max(0, min(len(bell), n - b0))]
        out[b0:b0 + len(bl)] += (bl * 0.35)[:, None]
        v0 = start + int(0.9 * SR)
        vv = v[: max(0, n - v0)]
        out[v0:v0 + len(vv)] += (vv * 0.95)[:, None]
        # la musica scende a un quarto mentre parla la voce (con rampe morbide)
        lo, hi = max(0, v0 - int(0.4 * SR)), min(n, v0 + len(vv) + int(0.5 * SR))
        gain[lo:hi] = np.minimum(gain[lo:hi], 0.25)
    k = int(0.4 * SR)                                  # media mobile con le somme cumulate: veloce anche su 10 minuti
    c = np.concatenate([[0.0], np.cumsum(gain, dtype=np.float64)])
    idx = np.arange(n)
    lo_i, hi_i = np.clip(idx - k // 2, 0, n), np.clip(idx + k // 2, 0, n)
    smooth = ((c[hi_i] - c[lo_i]) / np.maximum(hi_i - lo_i, 1)).astype(np.float32)
    out += bed * smooth[:, None]
    peak = float(np.abs(out).max()) or 1.0
    return (out * (0.9 / peak)).astype(np.float32)


def _to_mp3(samples: np.ndarray, out: Path) -> Path:
    from .video.music import write_wav
    from .video.render import ffmpeg_path
    with tempfile.TemporaryDirectory() as tmp:
        wav = write_wav(samples, Path(tmp) / "radio.wav")
        r = subprocess.run([ffmpeg_path(), "-y", "-loglevel", "error", "-i", str(wav), "-b:a", "128k", str(out)],
                           capture_output=True, text=True, timeout=600,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode != 0 or not out.exists():
        raise RadioError("Conversione in MP3 non riuscita.")
    return out


def make_program(store: Store, texts: list[str], engine: str, minutes: int, out: Path) -> Path:
    """Il programma della radio: `minutes` minuti con gli annunci distribuiti, pronto da mandare in loop."""
    texts = [t.strip() for t in texts if t and t.strip()][:MAX_ANNOUNCEMENTS]
    if not texts:
        raise RadioError("Scrivi almeno un annuncio.")
    if minutes not in MINUTES:
        raise RadioError("Durata non valida.")
    if any(len(t) > 600 for t in texts):
        raise RadioError("Un annuncio è troppo lungo: tienilo sotto le 600 lettere.")
    voices = []
    with tempfile.TemporaryDirectory() as tmp:
        for i, t in enumerate(texts):
            voices.append(_read_mono(accessible.speak_wav(store, t, engine, Path(tmp) / f"a{i}.wav")))
    total_voice = sum(len(v) for v in voices) / SR + 2.2 * len(voices)
    seconds = max(minutes * 60, total_voice + 10)
    return _to_mp3(mix(voices, seconds), out)


def make_closing(store: Store, engine: str, out: Path, minutes: int = 15) -> Path:
    with tempfile.TemporaryDirectory() as tmp:
        v = _read_mono(accessible.speak_wav(store, closing(store, minutes), engine, Path(tmp) / "c.wav"))
    return _to_mp3(mix([v], len(v) / SR + 4.0, seed=3), out)
