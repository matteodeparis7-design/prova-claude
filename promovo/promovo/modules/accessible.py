"""Volantino accessibile: da ascoltare e a caratteri grandi.

In Italia quasi una persona su quattro ha più di 65 anni (ISTAT). Molte leggono a fatica il volantino, ma ascoltano
volentieri i messaggi vocali. Dalla stessa lettura del volantino Promovo prepara:

- il volantino da ascoltare: un audio di circa un minuto con le offerte principali, da mandare su WhatsApp.
  La voce è quella italiana di Windows (gratuita, sul computer) oppure la voce del negozio (ElevenLabs, se
  configurata). È una voce sintetica: il testo lo dice all'inizio, per trasparenza;
- il volantino a caratteri grandi: un A4 ad alto contrasto, leggibile senza occhiali, da tenere alla cassa.

Il testo letto è solo quello del volantino: nomi, formati, prezzi e date. Niente aggettivi inventati.
"""
from __future__ import annotations

import platform
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

from ..models import Flyer, Store
from ..money import format_eur
from .content.service import featured_offers
from .video.render import INK, WHITE, fit_text, font, hex_rgb, readable_on_paper, text_layer
from .. import voice as voicemod

MAX_OFFERS = 10
DAYS = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
MONTHS = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre",
          "ottobre", "novembre", "dicembre"]


class AudioError(RuntimeError):
    pass


# ----------------------------------------------------------------- il testo da leggere

def _day(d) -> str:
    return f"{DAYS[d.weekday()]} {d.day} {MONTHS[d.month - 1]}"


def script(store: Store, flyer: Flyer, limit: int = MAX_OFFERS) -> str:
    """Il testo del volantino da ascoltare, già scritto come si legge (prezzi e misure in parole)."""
    offers = featured_offers(flyer, limit)
    parts = [f"Buongiorno da {store.name}. Questo messaggio è letto da una voce sintetica.",
             "Ecco le offerte della settimana"
             + (f", valide da {_day(flyer.valid_from)} a {_day(flyer.valid_to)}." if flyer.valid_from and flyer.valid_to
                else ".")]
    for o in offers:
        name = " ".join(x for x in (o.brand, o.name) if x)
        size = f", {o.description}" if o.description else ""
        line = f"{name}{size}: {format_eur(o.price_cents)}"
        if o.old_price_cents and o.old_price_cents > o.price_cents:
            line += f", invece di {format_eur(o.old_price_cents)}"
        parts.append(line + ".")
    from .content.writer import available
    rest = len(available(flyer)) - len(offers)
    if rest > 0:
        parts.append(f"E altre {rest} offerte nel volantino.")
    where = ", ".join(x for x in (store.address, store.city) if x)
    parts.append(f"Vi aspettiamo in {where}." if where else "Vi aspettiamo.")
    return voicemod.to_spoken(" ".join(parts))


def seconds(text: str) -> int:
    """Durata stimata (circa 2,6 parole al secondo, lettura calma)."""
    return max(5, round(len(text.split()) / 2.6))


# ----------------------------------------------------------------- le voci

def windows_voice() -> str | None:
    """Il nome della voce italiana di Windows, se c'è (es. «Microsoft Elsa Desktop»)."""
    if platform.system() != "Windows":
        return None
    ps = ("Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
          "$s.GetInstalledVoices() | Where-Object { $_.Enabled -and $_.VoiceInfo.Culture.Name -like 'it*' } | "
          "Select-Object -First 1 | ForEach-Object { $_.VoiceInfo.Name }")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], capture_output=True,
                           text=True, timeout=30, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        return None
    name = (r.stdout or "").strip().splitlines()
    return name[0].strip() if name and name[0].strip() else None


def engines(store: Store) -> list[dict]:
    """Le voci che si possono usare su questo computer, la migliore per prima."""
    out = []
    if store.voice_id and store.voice_consent_at and voicemod.api_key():
        out.append({"key": "negozio", "label": f"La voce del negozio ({store.voice_consent_name})", "ai": True})
    w = windows_voice()
    if w:
        out.append({"key": "windows", "label": f"Voce italiana di Windows ({w})", "ai": False})
    return out


def _windows_wav(text: str, out_wav: Path, voice: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "testo.txt"
        src.write_text(text, encoding="utf-8")
        q = lambda v: str(v).replace("'", "''")          # apici nei percorsi (es. «Dell'Acqua»)
        ps = ("Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
              f"$s.SelectVoice('{q(voice)}'); $s.Rate = -1; $s.SetOutputToWaveFile('{q(out_wav)}'); "
              f"$t = Get-Content -Raw -Encoding UTF8 '{q(src)}'; $s.Speak($t); $s.Dispose()")
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], capture_output=True,
                           text=True, timeout=180, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if r.returncode != 0 or not out_wav.exists() or out_wav.stat().st_size < 1000:
            raise AudioError("La voce di Windows non ha prodotto l'audio. " + (r.stderr or "")[:200])


def _to_mp3(src: Path, out: Path) -> Path:
    from .video.render import ffmpeg_path
    r = subprocess.run([ffmpeg_path(), "-y", "-loglevel", "error", "-i", str(src), "-ac", "1", "-ar", "44100",
                        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-b:a", "96k", str(out)],
                       capture_output=True, text=True, timeout=180,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode != 0 or not out.exists():
        raise AudioError("Conversione dell'audio non riuscita: " + (r.stderr or "")[:200])
    return out


def speak_wav(store: Store, text: str, engine: str, out_wav: Path) -> Path:
    """Legge un testo con la voce scelta e salva un WAV mono a 44,1 kHz (per montarlo, per esempio nella radio)."""
    from .video.render import ffmpeg_path
    with tempfile.TemporaryDirectory() as tmp:
        if engine == "negozio":
            key = voicemod.api_key()
            if not (store.voice_id and store.voice_consent_at and key):
                raise AudioError("La voce del negozio non è configurata.")
            raw = voicemod.synthesize(text, store.voice_id, Path(tmp) / "voce.mp3", key)
        elif engine == "windows":
            v = windows_voice()
            if not v:
                raise AudioError("Su questo computer non c'è la voce italiana di Windows: si aggiunge da "
                                 "Impostazioni → Ora e lingua → Voce → Aggiungi voci → Italiano.")
            raw = Path(tmp) / "voce.wav"
            _windows_wav(text, raw, v)
        else:
            raise AudioError("Voce non disponibile.")
        out_wav.parent.mkdir(parents=True, exist_ok=True)
        r = subprocess.run([ffmpeg_path(), "-y", "-loglevel", "error", "-i", str(raw), "-ac", "1", "-ar", "44100",
                            "-sample_fmt", "s16", str(out_wav)], capture_output=True, text=True, timeout=120,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if r.returncode != 0 or not out_wav.exists():
            raise AudioError("Conversione della voce non riuscita.")
    return out_wav


def make_audio(store: Store, text: str, out_mp3: Path, engine: str) -> Path:
    """Legge il testo con la voce scelta e salva un MP3 pronto per WhatsApp."""
    if len(text.strip()) < 10:
        raise AudioError("Il testo da leggere è vuoto.")
    if len(text) > 2500:
        raise AudioError("Il testo è troppo lungo per un messaggio vocale (al massimo circa 3 minuti).")
    out_mp3.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        if engine == "negozio":
            key = voicemod.api_key()
            if not (store.voice_id and store.voice_consent_at and key):
                raise AudioError("La voce del negozio non è configurata.")
            raw = voicemod.synthesize(text, store.voice_id, Path(tmp) / "voce.mp3", key)
        elif engine == "windows":
            v = windows_voice()
            if not v:
                raise AudioError("Su questo computer non c'è la voce italiana di Windows: si aggiunge da "
                                 "Impostazioni → Ora e lingua → Voce → Aggiungi voci → Italiano.")
            raw = Path(tmp) / "voce.wav"
            _windows_wav(text, raw, v)
        else:
            raise AudioError("Voce non disponibile.")
        return _to_mp3(raw, out_mp3)


# ----------------------------------------------------------------- a caratteri grandi

def large_print_pages(store: Store, flyer: Flyer) -> list[Image.Image]:
    W, H = 1654, 2339                                    # A4 a 200 dpi
    brand = hex_rgb(store.brand_color)
    ink = readable_on_paper(brand)
    offers = featured_offers(flyer, len(flyer.offers))
    per_page = 5
    pages = []
    for start in range(0, max(1, len(offers)), per_page):
        img = Image.new("RGB", (W, H), WHITE)
        d = ImageDraw.Draw(img)
        pad = 90
        d.rectangle((0, 0, W, 300), fill=INK)
        ft, lt = fit_text(store.name, W - 2 * pad, 110, 88, "display", 1)
        d.text((pad, 110), lt[0], font=ft, fill=WHITE, anchor="lm")
        sub = "Le offerte della settimana"
        if flyer.valid_from and flyer.valid_to:
            sub += f" · dal {flyer.valid_from.day}/{flyer.valid_from.month} al {flyer.valid_to.day}/{flyer.valid_to.month}"
        fs, ls = fit_text(sub, W - 2 * pad, 70, 56, True, 1)
        d.text((pad, 220), ls[0], font=fs, fill=WHITE, anchor="lm")
        y = 360
        row_h = (H - 360 - 200) // per_page
        for o in offers[start:start + per_page]:
            name = " ".join(x for x in (o.brand, o.name) if x)
            fn, ln = fit_text(name, W - 2 * pad - 560, row_h - 110, 72, True, 2, min_size=48)
            nl = text_layer(ln, fn, INK)
            img.paste(nl, (pad, y + 20), nl)
            if o.description:
                d.text((pad, y + 30 + nl.height), o.description, font=font(54), fill=(60, 64, 76))
            d.text((W - pad, y + row_h // 2 - 20), format_eur(o.price_cents), font=font(118, "display"), fill=ink,
                   anchor="rm")
            if o.old_price_cents and o.old_price_cents > o.price_cents:
                d.text((W - pad, y + row_h // 2 + 70), f"invece di {format_eur(o.old_price_cents)}", font=font(46),
                       fill=(60, 64, 76), anchor="rm")
            d.line((pad, y + row_h - 6, W - pad, y + row_h - 6), fill=(0, 0, 0), width=4)
            y += row_h
        where = ", ".join(x for x in (store.address, store.city) if x)
        contact = " · ".join(x for x in (where, f"tel. {store.phone}" if store.phone else "") if x)
        fc, lc = fit_text(contact or store.name, W - 2 * pad, 60, 48, True, 1)
        d.text((W // 2, H - 120), lc[0], font=fc, fill=INK, anchor="mm")
        d.text((W // 2, H - 60), f"Pagina {len(pages) + 1}", font=font(36), fill=(60, 64, 76), anchor="mm")
        pages.append(img)
    return pages


def large_print_pdf(store: Store, flyer: Flyer, out: Path) -> Path:
    if not flyer.offers:
        raise AudioError("Il volantino non ha offerte.")
    pages = large_print_pages(store, flyer)
    out.parent.mkdir(parents=True, exist_ok=True)
    pages[0].save(out, "PDF", resolution=200, save_all=True, append_images=pages[1:])
    return out
