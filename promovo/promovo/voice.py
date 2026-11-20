"""La voce del negozio: voce sintetica (clonata, con consenso) tramite ElevenLabs.

Due modi di dare la voce ai video "dal banco":
1. il titolare registra la sua voce vera dal telefono o dal computer (non serve nulla di esterno);
2. voce clonata: il titolare registra una volta un campione, firma il consenso, e da quel momento
   Promovo legge i testi con la sua voce. Serve una chiave ElevenLabs (variabile ELEVENLABS_API_KEY
   o file CHIAVE_VOCE.txt accanto al file di avvio). I video con voce sintetica riportano sempre
   la scritta "Voce generata con IA" (AI Act, art. 50, obbligo in vigore dal 2 agosto 2026).
"""
from __future__ import annotations

import os
from pathlib import Path

import httpx

API = "https://api.elevenlabs.io/v1"
MODEL = "eleven_multilingual_v2"


class VoiceError(RuntimeError):
    pass


def api_key() -> str | None:
    key = (os.environ.get("ELEVENLABS_API_KEY") or "").strip()
    return key or None


def _client(client: httpx.Client | None) -> httpx.Client:
    return client or httpx.Client(timeout=httpx.Timeout(60.0, connect=15.0))


def _check(r: httpx.Response, what: str) -> None:
    if r.status_code == 401:
        raise VoiceError("Chiave ElevenLabs non valida.")
    if r.status_code == 429:
        raise VoiceError("Limite di utilizzo di ElevenLabs raggiunto: riprova più tardi.")
    if r.status_code >= 400:
        try:
            detail = r.json().get("detail")
            msg = detail.get("message") if isinstance(detail, dict) else str(detail)
        except ValueError:
            msg = r.text[:200]
        raise VoiceError(f"{what}: {msg or r.status_code}")


def clone_voice(name: str, samples: list[Path], key: str, client: httpx.Client | None = None) -> str:
    """Crea la voce clonata dai campioni registrati. Restituisce l'identificativo della voce."""
    if not samples:
        raise VoiceError("Serve almeno una registrazione della voce.")
    files = [("files", (p.name, p.read_bytes(), "audio/mpeg")) for p in samples]
    c = _client(client)
    try:
        r = c.post(f"{API}/voices/add", headers={"xi-api-key": key},
                   data={"name": name[:90], "description": "Voce del negozio per Promovo (con consenso)",
                         "remove_background_noise": "true"}, files=files)
    except httpx.HTTPError as exc:
        raise VoiceError(f"ElevenLabs non raggiungibile: {exc}") from exc
    finally:
        if client is None:
            c.close()
    _check(r, "Creazione della voce non riuscita")
    voice_id = r.json().get("voice_id")
    if not voice_id:
        raise VoiceError("ElevenLabs non ha restituito la voce.")
    return voice_id


def delete_voice(voice_id: str, key: str, client: httpx.Client | None = None) -> None:
    c = _client(client)
    try:
        r = c.delete(f"{API}/voices/{voice_id}", headers={"xi-api-key": key})
    except httpx.HTTPError as exc:
        raise VoiceError(f"ElevenLabs non raggiungibile: {exc}") from exc
    finally:
        if client is None:
            c.close()
    if r.status_code not in (200, 404):
        _check(r, "Eliminazione della voce non riuscita")


def synthesize(text: str, voice_id: str, out_path: Path, key: str, client: httpx.Client | None = None) -> Path:
    """Legge il testo con la voce indicata e salva un MP3."""
    if not text.strip():
        raise VoiceError("Testo della voce vuoto.")
    c = _client(client)
    try:
        r = c.post(f"{API}/text-to-speech/{voice_id}", params={"output_format": "mp3_44100_128"},
                   headers={"xi-api-key": key, "Accept": "audio/mpeg"},
                   json={"text": text, "model_id": MODEL, "language_code": "it",
                         "voice_settings": {"stability": 0.5, "similarity_boost": 0.8, "style": 0.15}})
    except httpx.HTTPError as exc:
        raise VoiceError(f"ElevenLabs non raggiungibile: {exc}") from exc
    finally:
        if client is None:
            c.close()
    _check(r, "Lettura del testo non riuscita")
    if not r.content:
        raise VoiceError("ElevenLabs ha restituito un audio vuoto.")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(r.content)
    return out_path


def spoken_price(cents: int) -> str:
    """12,99 -> "12 euro e 99": così la voce sintetica non sbaglia la lettura."""
    euros, c = divmod(int(cents), 100)
    if c == 0:
        return f"{euros} euro"
    if euros == 0:
        return f"{c} centesimi"
    return f"{euros} euro e {c:02d}"


_PRICE = r"(\d{1,4}),(\d{2})"


def to_spoken(text: str) -> str:
    """Testo scritto -> testo da leggere: prezzi, unità di misura e simboli come si dicono."""
    import re
    s = text
    s = re.sub(rf"€\s?{_PRICE}", lambda m: spoken_price(int(m.group(1)) * 100 + int(m.group(2))), s)
    s = re.sub(rf"{_PRICE}\s?(?:€|euro\b)", lambda m: spoken_price(int(m.group(1)) * 100 + int(m.group(2))), s)
    s = re.sub(r"\bal kg\b", "al chilo", s, flags=re.I)
    s = re.sub(r"\bal l\b|\bal litro\b", "al litro", s, flags=re.I)
    s = re.sub(r"\b1\s?kg\b", "1 chilo", s)
    s = re.sub(r"(\d)\s?kg\b", r"\1 chili", s)
    s = re.sub(r"(\d)\s?g\b", r"\1 grammi", s)
    s = re.sub(r"(\d)\s?ml\b", r"\1 millilitri", s)
    s = re.sub(r"(\d)\s?cl\b", r"\1 centilitri", s)
    s = re.sub(r"\b1\s?[lL]\b", "1 litro", s)
    s = re.sub(r"(\d)\s?[lL]\b", r"\1 litri", s)
    # orari: «lun-sab 8:00-20:00» -> «dal lunedì al sabato dalle 8 alle 20»
    days = {"lun": "lunedì", "mar": "martedì", "mer": "mercoledì", "gio": "giovedì", "ven": "venerdì",
            "sab": "sabato", "dom": "domenica"}
    d = "|".join(days)
    s = re.sub(rf"\b({d})\.?\s?[-–]\s?({d})\b\.?", lambda m: f"dal {days[m.group(1).lower()]} al "
               f"{days[m.group(2).lower()]}".replace("dal domenica", "dalla domenica").replace("al domenica", "alla domenica"),
               s, flags=re.I)
    s = re.sub(rf"\b({d})\.?(?=\s+\d{{1,2}}[:.]\d{{2}})", lambda m: days[m.group(1).lower()], s, flags=re.I)

    def hh(h: str, m: str) -> str:
        return str(int(h)) + ("" if m == "00" else f" e {int(m)}")
    s = re.sub(r"\b(\d{1,2})[:.](\d{2})\s?[-–]\s?(\d{1,2})[:.](\d{2})\b",
               lambda m: f"dalle {hh(m.group(1), m.group(2))} alle {hh(m.group(3), m.group(4))}", s)
    s = re.sub(r"(\d+)\s?x\s?(\d+)", r"\1 per \2", s)
    s = s.replace("%", " per cento").replace("&", " e ").replace("/", " o ")
    return re.sub(r"\s{2,}", " ", s).strip()
