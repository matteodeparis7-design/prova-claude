"""Le chiavi facoltative (IA di Anthropic, voce di ElevenLabs), inserite dalla pagina Impostazioni.

Restano sul computer, nella cartella dei dati di Promovo (file chiavi.json), e non vengono mai
mostrate per intero: nelle pagine si vede solo l'inizio e la fine. Promovo funziona anche senza:
gli agenti lavorano da soli; le chiavi aggiungono la lettura con l'IA e la voce generata.
"""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

from .config import Settings

log = logging.getLogger("promovo.keys")

SERVICES = {"ai": "ANTHROPIC_API_KEY", "voice": "ELEVENLABS_API_KEY"}
TEST_MODEL = "claude-haiku-5-5"        # la prova della chiave costa una frazione di centesimo


class KeyError_(ValueError):
    pass


def _file(settings: Settings) -> Path:
    return settings.data_dir / "chiavi.json"


def _load(settings: Settings) -> dict[str, str]:
    try:
        data = json.loads(_file(settings).read_text(encoding="utf-8"))
        return {k: str(v) for k, v in data.items() if k in SERVICES and v}
    except (OSError, ValueError):
        return {}


def get(settings: Settings, service: str) -> str | None:
    """La chiave salvata in Promovo, oppure quella data all'avvio (variabile d'ambiente)."""
    return _load(settings).get(service) or (os.environ.get(SERVICES[service]) or "").strip() or None


def source(settings: Settings, service: str) -> str:
    if _load(settings).get(service):
        return "impostazioni"
    return "avvio" if (os.environ.get(SERVICES[service]) or "").strip() else ""


def save(settings: Settings, service: str, key: str) -> None:
    data = _load(settings)
    data[service] = key
    path = _file(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    tmp.replace(path)
    if service == "voice":
        os.environ[SERVICES["voice"]] = key          # il modulo della voce la legge da qui


def remove(settings: Settings, service: str) -> None:
    data = _load(settings)
    data.pop(service, None)
    path = _file(settings)
    if data:
        path.write_text(json.dumps(data), encoding="utf-8")
    else:
        path.unlink(missing_ok=True)
    os.environ.pop(SERVICES[service], None)


def mask(key: str | None) -> str:
    if not key:
        return ""
    return f"{key[:7]}…{key[-4:]}" if len(key) > 14 else "…" + key[-3:]


def clean(service: str, key: str) -> str:
    key = (key or "").strip().strip('"').strip("'")
    key = re.sub(r"\s+", "", key)
    if not key:
        raise KeyError_("Incolla la chiave.")
    if service == "ai" and not key.startswith("sk-ant-"):
        raise KeyError_("Questa non sembra una chiave Anthropic: deve iniziare con «sk-ant-». "
                        "La trovi su console.anthropic.com, nella sezione API Keys.")
    if len(key) < 20 or len(key) > 300:
        raise KeyError_("La chiave non ha la lunghezza giusta: controlla di averla copiata tutta.")
    return key


# ------------------------------------------------------------------ prova delle chiavi

def test_ai(key: str, client=None) -> None:
    """Una richiesta minima: verifica che la chiave sia valida e che ci sia credito."""
    import anthropic
    client = client or anthropic.Anthropic(api_key=key, max_retries=1, timeout=30)
    try:
        client.messages.create(model=TEST_MODEL, max_tokens=1, messages=[{"role": "user", "content": "ok"}])
    except anthropic.AuthenticationError as exc:
        raise KeyError_("Chiave non valida: Anthropic non la riconosce. Copiala di nuovo dalla console.") from exc
    except anthropic.PermissionDeniedError as exc:
        raise KeyError_("La chiave non ha i permessi per usare i modelli: controlla l'account Anthropic.") from exc
    except anthropic.BadRequestError as exc:
        text = str(exc).lower()
        if "credit" in text or "balance" in text or "billing" in text:
            raise KeyError_("La chiave è giusta ma il credito è finito: ricaricalo su console.anthropic.com "
                            "(Billing). Bastano pochi euro per molti volantini.") from exc
        raise KeyError_(f"Anthropic ha rifiutato la prova: {exc}") from exc
    except anthropic.APIConnectionError as exc:
        raise KeyError_("Nessuna connessione con Anthropic: controlla internet e riprova.") from exc
    except anthropic.RateLimitError:
        return                                         # la chiave funziona, è solo occupata
    except anthropic.APIStatusError as exc:
        if exc.status_code >= 500:
            raise KeyError_("Il servizio di Anthropic è momentaneamente non disponibile: riprova tra poco.") from exc
        raise KeyError_(f"Anthropic ha risposto con un errore ({exc.status_code}).") from exc


def test_voice(key: str, client=None) -> None:
    import httpx
    c = client or httpx.Client(timeout=httpx.Timeout(20.0, connect=10.0))
    try:
        r = c.get("https://api.elevenlabs.io/v1/user", headers={"xi-api-key": key})
    except httpx.HTTPError as exc:
        raise KeyError_("Nessuna connessione con ElevenLabs: controlla internet e riprova.") from exc
    if r.status_code == 401:
        raise KeyError_("Chiave ElevenLabs non valida: copiala di nuovo dal tuo profilo ElevenLabs.")
    if r.status_code >= 400:
        raise KeyError_(f"ElevenLabs ha risposto con un errore ({r.status_code}).")


def make_llm(settings: Settings, client=None):
    """L'IA facoltativa, se c'è una chiave (altrimenti None: lavorano solo gli agenti)."""
    if settings.ai_mode == "off":
        return None
    key = get(settings, "ai")
    if not key and client is None:
        return None
    from .llm.client import ClaudeLLM
    try:
        import anthropic
        return ClaudeLLM(model=settings.model, client=client or anthropic.Anthropic(api_key=key))
    except Exception as exc:  # noqa: BLE001
        log.warning("IA facoltativa non attivabile: %s", exc)
        return None


def load_voice_key(settings: Settings) -> None:
    """All'avvio: la chiave della voce salvata nelle impostazioni diventa disponibile al modulo voce."""
    key = _load(settings).get("voice")
    if key:
        os.environ[SERVICES["voice"]] = key
