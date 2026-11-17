"""Verifica che ClaudeLLM costruisca le richieste giuste e gestisca risposte ed errori."""
from types import SimpleNamespace

import anthropic
import httpx
import pytest
from pydantic import BaseModel

from promovo.llm import AIRefused, AIUnavailable, ClaudeLLM, DisabledLLM, ToolSpec, get_llm


class Out(BaseModel):
    value: int


class Block(SimpleNamespace):
    def model_dump(self, **_):
        return {k: v for k, v in self.__dict__.items()}


class FakeMessages:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def _next(self, kwargs):
        self.requests.append(kwargs)
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    def parse(self, **kwargs):
        return self._next(kwargs)

    def create(self, **kwargs):
        return self._next(kwargs)


def client_with(responses):
    msgs = FakeMessages(responses)
    return SimpleNamespace(beta=SimpleNamespace(messages=msgs)), msgs


def test_parse_request_shape_and_result():
    client, msgs = client_with([SimpleNamespace(stop_reason="end_turn", parsed_output=Out(value=7))])
    llm = ClaudeLLM("claude-opus-5-5", client=client)
    out = llm.parse(system="sys", content=[{"type": "text", "text": "ciao"}], schema=Out, effort="high")
    assert out.value == 7
    req = msgs.requests[0]
    assert req["model"] == "claude-opus-5-5"
    assert req["output_format"] is Out
    assert req["output_config"] == {"effort": "high"}
    assert req["fallbacks"] == "default" and req["betas"] == ["server-side-fallback-2026-07-01"]
    assert "thinking" not in req and "temperature" not in req
    assert req["messages"] == [{"role": "user", "content": [{"type": "text", "text": "ciao"}]}]


@pytest.mark.parametrize("resp,exc", [
    (SimpleNamespace(stop_reason="refusal", parsed_output=None), AIRefused),
    (SimpleNamespace(stop_reason="max_tokens", parsed_output=None), AIUnavailable),
    (SimpleNamespace(stop_reason="end_turn", parsed_output=None), AIUnavailable),
])
def test_parse_bad_outcomes(resp, exc):
    client, _ = client_with([resp])
    with pytest.raises(exc):
        ClaudeLLM("m", client=client).parse(system="s", content=[], schema=Out)


def _status_error(cls, code):
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls("errore", response=httpx.Response(code, request=req), body=None)


@pytest.mark.parametrize("err", [
    _status_error(anthropic.AuthenticationError, 401),
    _status_error(anthropic.RateLimitError, 429),
    _status_error(anthropic.InternalServerError, 500),
    anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com")),
    TypeError("Could not resolve authentication method."),
])
def test_parse_api_errors_become_unavailable(err):
    client, _ = client_with([err])
    with pytest.raises(AIUnavailable):
        ClaudeLLM("m", client=client).parse(system="s", content=[], schema=Out)


def test_other_type_errors_are_not_hidden():
    client, _ = client_with([TypeError("bug nel codice")])
    with pytest.raises(TypeError):
        ClaudeLLM("m", client=client).parse(system="s", content=[], schema=Out)


def test_tool_loop():
    seen = []
    tool = ToolSpec("somma", "Somma", {"type": "object", "additionalProperties": False,
                                        "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
                                        "required": ["a", "b"]},
                    lambda args: seen.append(args) or {"risultato": args["a"] + args["b"]})
    broken = ToolSpec("rotto", "Fallisce", {"type": "object", "additionalProperties": False, "properties": {},
                                            "required": []}, lambda args: 1 / 0)
    r1 = SimpleNamespace(stop_reason="tool_use", content=[
        Block(type="thinking", thinking="", signature="sig"),
        Block(type="tool_use", id="t1", name="somma", input={"a": 2, "b": 3}),
        Block(type="tool_use", id="t2", name="rotto", input={}),
        Block(type="tool_use", id="t3", name="inesistente", input={}),
    ])
    r2 = SimpleNamespace(stop_reason="pause_turn", content=[Block(type="text", text="...")])
    r3 = SimpleNamespace(stop_reason="end_turn", content=[Block(type="text", text="Fa 5.")])
    client, msgs = client_with([r1, r2, r3])
    res = ClaudeLLM("m", client=client).run_tools(system="s", messages=[{"role": "user", "content": "2+3?"}],
                                                  tools=[tool, broken])
    assert res.text == "Fa 5."
    assert seen == [{"a": 2, "b": 3}]
    # Tutti i risultati in UN solo messaggio, con gli errori segnalati.
    results = res.messages[2]["content"]
    assert [r["tool_use_id"] for r in results] == ["t1", "t2", "t3"]
    assert '"risultato": 5' in results[0]["content"] and "is_error" not in results[0]
    assert results[1]["is_error"] and results[2]["is_error"]
    # Il blocco di ragionamento viene rimandato intatto.
    assert res.messages[1]["content"][0] == {"type": "thinking", "thinking": "", "signature": "sig"}
    defs = msgs.requests[0]["tools"]
    assert defs[0]["strict"] is True and defs[0]["name"] == "somma"
    assert len(msgs.requests) == 3


def test_tool_loop_limits_and_refusal():
    loop = SimpleNamespace(stop_reason="tool_use", content=[Block(type="tool_use", id="t", name="x", input={})])
    client, _ = client_with([loop] * 3)
    with pytest.raises(AIUnavailable, match="massimo"):
        ClaudeLLM("m", client=client).run_tools(system="s", messages=[], tools=[], max_turns=3)
    client, _ = client_with([SimpleNamespace(stop_reason="refusal", content=[])])
    with pytest.raises(AIRefused):
        ClaudeLLM("m", client=client).run_tools(system="s", messages=[], tools=[])


def test_disabled_llm():
    llm = get_llm("off", "m")
    assert isinstance(llm, DisabledLLM)
    with pytest.raises(AIUnavailable):
        llm.parse(system="s", content=[], schema=Out)
    with pytest.raises(AIUnavailable):
        llm.run_tools(system="s", messages=[], tools=[])
