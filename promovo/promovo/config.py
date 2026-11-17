"""Configurazione letta dalle variabili d'ambiente.

Nessun segreto è scritto nel codice: la chiave Anthropic viene letta dall'SDK
(ANTHROPIC_API_KEY o un profilo `ant auth login`).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _env(name: str, default: str) -> str:
    value = os.environ.get(name, "").strip()
    return value or default


@dataclass(frozen=True)
class Settings:
    database_url: str = field(default_factory=lambda: _env("PROMOVO_DATABASE_URL", "sqlite:///./promovo.db"))
    data_dir: Path = field(default_factory=lambda: Path(_env("PROMOVO_DATA_DIR", "./promovo_data")).resolve())
    # Modello principale per tutti gli agenti.
    model: str = field(default_factory=lambda: _env("PROMOVO_MODEL", "claude-opus-5-5"))
    # "claude" usa l'API reale; "off" disattiva l'IA (si usano solo i metodi senza IA).
    ai_mode: str = field(default_factory=lambda: _env("PROMOVO_AI", "claude"))
    # Durata dei token di accesso, in ore.
    token_ttl_hours: int = field(default_factory=lambda: int(_env("PROMOVO_TOKEN_TTL_HOURS", "720")))
    # Dimensione massima dei PDF caricati, in MB.
    max_upload_mb: int = field(default_factory=lambda: int(_env("PROMOVO_MAX_UPLOAD_MB", "40")))

    def ensure_dirs(self) -> None:
        for sub in ("flyers", "renders", "crops"):
            (self.data_dir / sub).mkdir(parents=True, exist_ok=True)


def get_settings() -> Settings:
    return Settings()
