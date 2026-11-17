"""Livello IA: un'unica interfaccia usata da tutti gli agenti.

- ClaudeLLM: usa l'API di Anthropic (output strutturati + ciclo di strumenti).
- DisabledLLM: IA spenta; ogni chiamata solleva AIUnavailable, così i moduli
  passano ai metodi senza IA invece di inventare risultati.
- Nei test si usa un LLM finto che implementa la stessa interfaccia.
"""
from __future__ import annotations

import base64
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

log = logging.getLogger("promovo.llm")

T = TypeVar("T", bound=BaseModel)

# Fallback lato server: se il modello rifiuta per una categoria di sicurezza, l'API
# riprova da sola su un modello adatto, nella stessa chiamata.
_FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AIUnavailable(RuntimeError):
    """L'IA non è configurata o non è raggiungibile."""


class AIRefused(RuntimeError):
    """Il modello ha rifiutato la richiesta."""


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict
    handler: Callable[[dict], Any]

    def definition(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "strict": True,
        }


@dataclass
class ToolRunResult:
    text: str
    messages: list[dict]
    tool_calls: list[dict] = field(default_factory=list)


class LLM(Protocol):
    def parse(self, *, system: str, content: list[dict], schema: type[T], effort: str = "medium",
              max_tokens: int = 16000) -> T: ...

    def run_tools(self, *, system: str, messages: list[dict], tools: list[ToolSpec], effort: str = "low",
                  max_turns: int = 8, max_tokens: int = 8000) -> ToolRunResult: ...


def image_block(png_bytes: bytes, media_type: str = "image/png") -> dict:
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": media_type,
                   "data": base64.standard_b64encode(png_bytes).decode("ascii")},
    }


def _to_param(block: Any) -> dict:
    """Converte un blocco di risposta dell'SDK in un dict riutilizzabile nella cronologia."""
    if isinstance(block, dict):
        return block
    if hasattr(block, "model_dump"):
        return block.model_dump(exclude_none=True, mode="json")
    raise TypeError(f"Blocco non serializzabile: {type(block)!r}")


def _run_tool(tool: ToolSpec, args: dict) -> tuple[str, bool]:
    try:
        result = tool.handler(args)
    except Exception as exc:  # l'errore torna al modello, che può correggersi
        log.warning("Strumento %s fallito: %s", tool.name, exc)
        return f"Errore: {exc}", True
    if isinstance(result, str):
        return result, False
    return json.dumps(result, ensure_ascii=False, default=str), False


def execute_tool_calls(tool_uses: list[Any], tools_by_name: dict[str, ToolSpec],
                       log_calls: list[dict]) -> list[dict]:
    """Esegue tutte le chiamate di un turno e restituisce i tool_result in un solo messaggio."""
    results = []
    for tu in tool_uses:
        name = tu.name if hasattr(tu, "name") else tu["name"]
        tu_id = tu.id if hasattr(tu, "id") else tu["id"]
        args = tu.input if hasattr(tu, "input") else tu["input"]
        tool = tools_by_name.get(name)
        if tool is None:
            content, is_error = f"Errore: strumento sconosciuto '{name}'.", True
        else:
            content, is_error = _run_tool(tool, dict(args or {}))
        log_calls.append({"name": name, "input": args, "is_error": is_error})
        block = {"type": "tool_result", "tool_use_id": tu_id, "content": content}
        if is_error:
            block["is_error"] = True
        results.append(block)
    return results


class ClaudeLLM:
    def __init__(self, model: str, client: Any | None = None):
        self.model = model
        if client is None:
            try:
                import anthropic
            except ImportError as exc:  # pragma: no cover
                raise AIUnavailable("Pacchetto 'anthropic' non installato.") from exc
            client = anthropic.Anthropic()
        self.client = client

    def _errors(self):
        import anthropic
        return anthropic

    def parse(self, *, system: str, content: list[dict], schema: type[T], effort: str = "medium",
              max_tokens: int = 16000) -> T:
        a = self._errors()
        try:
            response = self.client.beta.messages.parse(
                model=self.model,
                max_tokens=max_tokens,
                betas=[_FALLBACK_BETA],
                fallbacks="default",
                system=system,
                output_config={"effort": effort},
                output_format=schema,
                messages=[{"role": "user", "content": content}],
            )
        except a.AuthenticationError as exc:
            raise AIUnavailable("Chiave Anthropic non valida o mancante.") from exc
        except a.APIConnectionError as exc:
            raise AIUnavailable("API Anthropic non raggiungibile.") from exc
        except a.RateLimitError as exc:
            raise AIUnavailable("Limite di richieste raggiunto, riprova tra poco.") from exc
        except a.APIStatusError as exc:
            raise AIUnavailable(f"Errore dell'API Anthropic ({exc.status_code}).") from exc
        except TypeError as exc:
            if "authentication" in str(exc).lower():
                raise AIUnavailable("Chiave Anthropic non configurata.") from exc
            raise
        if response.stop_reason == "refusal":
            raise AIRefused("Il modello ha rifiutato la richiesta.")
        if response.stop_reason == "max_tokens":
            raise AIUnavailable("Risposta troppo lunga: aumentare max_tokens o dividere il lavoro.")
        parsed = response.parsed_output
        if parsed is None:
            raise AIUnavailable("Risposta dell'IA non valida.")
        return parsed

    def run_tools(self, *, system: str, messages: list[dict], tools: list[ToolSpec], effort: str = "low",
                  max_turns: int = 8, max_tokens: int = 8000) -> ToolRunResult:
        a = self._errors()
        msgs = list(messages)
        by_name = {t.name: t for t in tools}
        calls: list[dict] = []
        response = None
        for _ in range(max_turns):
            try:
                response = self.client.beta.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    betas=[_FALLBACK_BETA],
                    fallbacks="default",
                    system=system,
                    output_config={"effort": effort},
                    tools=[t.definition() for t in tools],
                    messages=msgs,
                )
            except a.AuthenticationError as exc:
                raise AIUnavailable("Chiave Anthropic non valida o mancante.") from exc
            except a.APIConnectionError as exc:
                raise AIUnavailable("API Anthropic non raggiungibile.") from exc
            except a.RateLimitError as exc:
                raise AIUnavailable("Limite di richieste raggiunto, riprova tra poco.") from exc
            except a.APIStatusError as exc:
                raise AIUnavailable(f"Errore dell'API Anthropic ({exc.status_code}).") from exc
            except TypeError as exc:
                if "authentication" in str(exc).lower():
                    raise AIUnavailable("Chiave Anthropic non configurata.") from exc
                raise

            msgs.append({"role": "assistant", "content": [_to_param(b) for b in response.content]})
            if response.stop_reason == "pause_turn":
                continue
            if response.stop_reason != "tool_use":
                break
            tool_uses = [b for b in response.content if b.type == "tool_use"]
            msgs.append({"role": "user", "content": execute_tool_calls(tool_uses, by_name, calls)})
        else:
            raise AIUnavailable("L'assistente ha superato il numero massimo di passaggi.")

        if response is not None and response.stop_reason == "refusal":
            raise AIRefused("Il modello ha rifiutato la richiesta.")
        text = "".join(b.text for b in response.content if b.type == "text").strip() if response else ""
        return ToolRunResult(text=text, messages=msgs, tool_calls=calls)


class DisabledLLM:
    def parse(self, **_: Any):
        raise AIUnavailable("IA disattivata (PROMOVO_AI=off).")

    def run_tools(self, **_: Any):
        raise AIUnavailable("IA disattivata (PROMOVO_AI=off).")


def get_llm(ai_mode: str, model: str) -> LLM:
    if ai_mode == "off":
        return DisabledLLM()
    return ClaudeLLM(model=model)
