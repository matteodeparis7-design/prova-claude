"""Versione di Promovo e build (scritta dalla costruzione automatica per Windows, se c'è)."""
from __future__ import annotations

import json
from pathlib import Path

VERSION = "0.9 beta"
RELEASES_API = "https://api.github.com/repos/matteodeparis7-design/prova-claude/releases/tags/promovo-beta"
RELEASES_PAGE = "https://github.com/matteodeparis7-design/prova-claude/releases/tag/promovo-beta"


def build() -> dict:
    """{"commit": ..., "date": ...} della build in uso; vuoto quando si lavora dai sorgenti."""
    p = Path(__file__).resolve().parent / "build_info.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
