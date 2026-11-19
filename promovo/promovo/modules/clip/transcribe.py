"""Sottotitoli a tempo di parola per i Reel «Dal banco» (Whisper small via faster-whisper, licenze MIT).

Tutto sul computer: la voce non esce mai. Due casi:
- il negoziante ha letto il testo proposto: i sottotitoli riportano quel testo esatto (niente errori di
  trascrizione), ma ogni parola compare quando viene davvero detta (tempi presi dalla trascrizione);
- ha parlato a braccio: i sottotitoli sono la trascrizione, aiutata dai nomi dei prodotti del volantino.
Se il modello non è installato o qualcosa va storto si torna al metodo di prima (tempi stimati).
"""
from __future__ import annotations

import difflib
import logging
import re
import subprocess
import threading
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from ... import extras

log = logging.getLogger("promovo.transcribe")
_model = None
_lock = threading.Lock()


@dataclass
class Word:
    text: str
    start: float
    end: float


def available() -> bool:
    return extras.path("subtitles") is not None


def _load():
    global _model
    if _model is None:
        folder = extras.path("subtitles")
        if folder is None:
            return None
        from faster_whisper import WhisperModel
        _model = WhisperModel(str(folder), device="cpu", compute_type="int8")
    return _model


def _audio(path: Path):
    """La voce come numeri a 16 kHz (con ffmpeg, lo stesso che monta i video)."""
    import numpy as np
    from ..video.render import ffmpeg_path
    raw = subprocess.run([ffmpeg_path(), "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", "16000", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)


def transcribe(path: Path, hint: str = "") -> list[Word] | None:
    """Le parole dette, con i loro tempi in secondi dall'inizio del file. None se non disponibile."""
    try:
        with _lock:
            model = _load()
            if model is None:
                return None
            segs, _ = model.transcribe(_audio(path), language="it", word_timestamps=True, vad_filter=True,
                                       beam_size=5, initial_prompt=(hint[:400] or None))
            words = [Word(w.word.strip(), float(w.start), float(w.end)) for s in segs for w in (s.words or [])]
        return [w for w in words if w.text]
    except Exception as exc:      # il sottotitolo non deve mai bloccare il Reel
        log.warning("trascrizione non riuscita: %s", exc)
        return None


def _key(w: str) -> str:
    w = unicodedata.normalize("NFD", w.lower())
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in w if unicodedata.category(c) != "Mn"))


def align(script: str, heard: list[Word]) -> list[Word] | None:
    """Il testo letto, parola per parola, con i tempi della trascrizione. None se non combaciano abbastanza."""
    words = script.split()
    if not words or not heard:
        return None
    a, b = [_key(w) for w in words], [_key(w.text) for w in heard]
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    times: list[tuple[float, float] | None] = [None] * len(words)
    matched = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                times[i1 + k] = (heard[j1 + k].start, heard[j1 + k].end)
                matched += 1
        elif tag == "replace" and j2 > j1:
            # parole lette in modo un po' diverso: il tratto di tempo si divide tra loro
            t0, t1 = heard[j1].start, heard[j2 - 1].end
            n = i2 - i1
            for k in range(n):
                times[i1 + k] = (t0 + (t1 - t0) * k / n, t0 + (t1 - t0) * (k + 1) / n)
    if matched < 0.6 * len(words):
        return None                 # ha detto altro: meglio la trascrizione
    # le parole senza tempo (saltate) prendono quello delle vicine
    for i in range(len(times)):
        if times[i] is None:
            prev = next((times[j] for j in range(i - 1, -1, -1) if times[j]), None)
            nxt = next((times[j] for j in range(i + 1, len(times)) if times[j]), None)
            t = prev[1] if prev else (nxt[0] if nxt else 0.0)
            times[i] = (t, nxt[0] if nxt else t + 0.3)
    return [Word(w, s, e) for w, (s, e) in zip(words, times)]


def timed_captions(words: list[Word], max_chars: int = 30) -> list[tuple[str, float, float]]:
    """Sottotitoli brevi e bilanciati (a capo alle virgole e a fine frase, mai una parola sola in riga),
    ognuno mostrato da quando si dice la sua prima parola a quando finisce l'ultima."""
    from .render import caption_chunks
    if not words:
        return []
    chunks = caption_chunks(" ".join(w.text for w in words), max_chars=max_chars)
    out: list[tuple[str, float, float]] = []
    i = 0
    for c in chunks:
        n = len(c.split())
        part = words[i:i + n]
        i += n
        if part:
            out.append((c, part[0].start, part[-1].end))
    if i < len(words) and out:           # sicurezza: parole rimaste attaccate all'ultimo sottotitolo
        t, a, _ = out[-1]
        out[-1] = (t + " " + " ".join(w.text for w in words[i:]), a, words[-1].end)
    # ogni sottotitolo resta finché non arriva il successivo (niente buchi che fanno lampeggiare)
    fixed = []
    for k, (t, a, b) in enumerate(out):
        nxt = out[k + 1][1] if k + 1 < len(out) else b + 0.4
        fixed.append((t, a, max(b, min(nxt, b + 0.8))))
    return fixed


def captions_for(voice: Path, script: str = "", hint: str = "") -> tuple[list[tuple[str, float, float]], str] | None:
    """Sottotitoli a tempo e testo finale per la voce. None se l'agente non è disponibile."""
    heard = transcribe(voice, hint=(script or (f"In offerta: {hint.lower()}." if hint else "")))
    if not heard:
        return None
    words = align(script, heard) if script.strip() else None
    used = words or heard
    return timed_captions(used), " ".join(w.text for w in used)
