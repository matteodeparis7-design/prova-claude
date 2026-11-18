"""Strumenti comuni ai test: un LLM finto e prevedibile, database e cartelle temporanee."""
from __future__ import annotations

import itertools
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable

import pytest

from promovo.config import Settings
from promovo.db import Database
from promovo.llm import AIUnavailable, ToolRunResult, ToolSpec
from promovo.llm.client import execute_tool_calls
from promovo.models import Organization, Store
from promovo.sample_flyer import build_sample_flyer


@dataclass
class _ToolUse:
    id: str
    name: str
    input: dict
    type: str = "tool_use"


class FakeLLM:
    """Implementa la stessa interfaccia di ClaudeLLM senza chiamare l'API.

    - parse: per ogni schema si registra una funzione che riceve il contenuto e restituisce il risultato.
    - run_tools: esegue un copione di passi; ogni passo è una lista di chiamate (nome, argomenti)
      oppure una stringa (la risposta finale). Gli strumenti vengono eseguiti davvero.
    """

    def __init__(self):
        self.parse_handlers: dict[str, Callable[[list[dict]], Any]] = {}
        self.scripts: list[list] = []
        self.calls: list[tuple[str, Any]] = []
        self.unavailable = False
        self._ids = itertools.count(1)

    def on_parse(self, schema_name: str, fn: Callable[[list[dict]], Any]) -> None:
        self.parse_handlers[schema_name] = fn

    def parse(self, *, system: str, content: list[dict], schema, effort: str = "medium", max_tokens: int = 16000):
        self.calls.append(("parse", schema.__name__))
        if self.unavailable:
            raise AIUnavailable("finto: non disponibile")
        handler = self.parse_handlers.get(schema.__name__)
        if handler is None:
            raise AIUnavailable(f"nessun handler per {schema.__name__}")
        result = handler(content)
        return result if isinstance(result, schema) else schema.model_validate(result)

    def run_tools(self, *, system: str, messages: list[dict], tools: list[ToolSpec], effort: str = "low",
                  max_turns: int = 8, max_tokens: int = 8000) -> ToolRunResult:
        self.calls.append(("run_tools", messages[-1]["content"]))
        if self.unavailable:
            raise AIUnavailable("finto: non disponibile")
        script = self.scripts.pop(0)
        msgs = list(messages)
        by_name = {t.name: t for t in tools}
        log: list[dict] = []
        for step in script:
            if isinstance(step, str):
                msgs.append({"role": "assistant", "content": [{"type": "text", "text": step}]})
                return ToolRunResult(text=step, messages=msgs, tool_calls=log)
            uses = [_ToolUse(f"toolu_{next(self._ids)}", name, args) for name, args in step]
            msgs.append({"role": "assistant", "content": [
                {"type": "tool_use", "id": u.id, "name": u.name, "input": u.input} for u in uses]})
            msgs.append({"role": "user", "content": execute_tool_calls(uses, by_name, log)})
        raise AssertionError("Il copione deve finire con una risposta di testo.")


@pytest.fixture
def tmp_settings(tmp_path: Path) -> Settings:
    s = Settings(database_url="sqlite://", data_dir=tmp_path / "data", model="test", ai_mode="off",
                 token_ttl_hours=24, max_upload_mb=10, weather=False)
    s.ensure_dirs()
    return s


@pytest.fixture
def db() -> Database:
    d = Database("sqlite://")
    d.create_all()
    return d


@pytest.fixture
def session(db: Database):
    s = db.new_session()
    yield s
    s.rollback()
    s.close()


@pytest.fixture
def store(session) -> Store:
    org = Organization(name="Agenzia Test")
    session.add(org)
    session.flush()
    st = Store(organization_id=org.id, name="Superstore Test", banner="Superstore", address="Via Roma 1",
               city="Colleferro", phone="06 1234567", opening_hours={"lun-sab": "8:00-20:00"},
               services=["ritiro in negozio"])
    session.add(st)
    session.flush()
    return st


@pytest.fixture(scope="session")
def sample_pdf() -> bytes:
    return build_sample_flyer()


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()


TODAY = date(2026, 11, 15)  # dentro il periodo del volantino di prova (13-22 novembre 2026)


# ------------------------------------------------------------------ utilità per i test delle API

def register(client, email="titolare@test.it", org="Agenzia Test"):
    r = client.post("/api/auth/register", json={"organization": org, "email": email, "password": "password123",
                                                "name": "Titolare"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def make_store(client, h, **kw):
    body = {"name": "Superstore Colleferro", "address": "Via Roma 1", "city": "Colleferro", **kw}
    r = client.post("/api/stores", json=body, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture(scope="module")
def live_pdf():
    """Volantino valido da ieri a tra 10 giorni: le offerte risultano attive oggi."""
    start, end = date.today() - timedelta(days=1), date.today() + timedelta(days=10)
    return build_sample_flyer(validity=f"Offerte valide dal {start:%d/%m/%Y} al {end:%d/%m/%Y}")


def upload(client, h, store_id, pdf):
    r = client.post(f"/api/stores/{store_id}/flyers", headers=h,
                    files={"file": ("volantino.pdf", pdf, "application/pdf")}, data={"title": ""})
    assert r.status_code == 202, r.text
    assert r.json()["status"] == "processing"
    # La lettura avviene in background; il client di test la completa prima di rispondere.
    flyer = client.get(f"/api/flyers/{r.json()['id']}", headers=h).json()
    assert flyer["status"] == "ready", flyer
    return flyer
