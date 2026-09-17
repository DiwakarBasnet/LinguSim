import json

import pytest

from app.config import get_settings
from app.services.scenario_loader import ScenarioLoader
from app.services.voice_agent import AssemblyAIRelay, AssemblyAIRelayError


def test_relay_requires_an_api_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ASSEMBLYAI_API_KEY", "")
    get_settings.cache_clear()
    try:
        scenario = ScenarioLoader().get("order_food")
        with pytest.raises(AssemblyAIRelayError, match="ASSEMBLYAI_API_KEY"):
            AssemblyAIRelay(scenario)
    finally:
        get_settings.cache_clear()


async def test_connect_translates_network_failures_into_relay_error(monkeypatch: pytest.MonkeyPatch):
    """A network blip, wrong/expired key, or AssemblyAI outage should never
    surface as a raw, unhandled exception — the WebSocket handler only knows
    how to gracefully report AssemblyAIRelayError to the client."""
    monkeypatch.setenv("ASSEMBLYAI_API_KEY", "some-key")
    get_settings.cache_clear()
    try:
        scenario = ScenarioLoader().get("order_food")
        relay = AssemblyAIRelay(scenario)

        async def fake_connect(*args, **kwargs):
            raise OSError("connection refused")

        monkeypatch.setattr("app.services.voice_agent.assemblyai_client.websockets.connect", fake_connect)

        with pytest.raises(AssemblyAIRelayError):
            await relay.connect()
    finally:
        get_settings.cache_clear()


class _FakeWebSocket:
    """A minimal async-iterable standing in for AssemblyAIRelay's real
    websockets connection, so events() can be tested without any network."""

    def __init__(self, incoming: list[dict]):
        self._incoming = incoming
        self.sent: list[dict] = []

    async def send(self, message: str) -> None:
        self.sent.append(json.loads(message))

    def __aiter__(self):
        return self._generator()

    async def _generator(self):
        for message in self._incoming:
            yield json.dumps(message)


async def test_tool_call_is_bridged_to_the_dictionary_mcp_server(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ASSEMBLYAI_API_KEY", "some-key")
    get_settings.cache_clear()
    try:
        scenario = ScenarioLoader().get("order_food_de")  # target_language "German"
        relay = AssemblyAIRelay(scenario)
        relay._ws = _FakeWebSocket(
            [
                {
                    "type": "tool.call",
                    "call_id": "call_1",
                    "name": "get_translation_hint",
                    "arguments": {"term": "yesterday"},
                },
                {"type": "session.ended"},
            ]
        )

        async def fake_call_dictionary_tool(self, term):
            assert term == "yesterday"
            return "gestern"

        monkeypatch.setattr(AssemblyAIRelay, "_call_dictionary_tool", fake_call_dictionary_tool)

        events = [event async for event in relay.events()]

        assert {"type": "hint", "term": "yesterday", "translation": "gestern", "level": 2} in events
        tool_result = next(m for m in relay._ws.sent if m["type"] == "tool.result")
        assert tool_result["call_id"] == "call_1"
        assert json.loads(tool_result["result"]) == {"translation": "gestern"}
    finally:
        get_settings.cache_clear()


async def test_tool_call_infers_level_3_for_a_multi_word_phrase(monkeypatch: pytest.MonkeyPatch):
    """The tool takes no hint_level argument (see the comment on _HINT_TOOLS
    for why — a second required param made the live model far less likely
    to call the tool at all), so the level shown to the browser is inferred
    from the term's word count instead."""
    monkeypatch.setenv("ASSEMBLYAI_API_KEY", "some-key")
    get_settings.cache_clear()
    try:
        scenario = ScenarioLoader().get("order_food_de")
        relay = AssemblyAIRelay(scenario)
        relay._ws = _FakeWebSocket(
            [
                {
                    "type": "tool.call",
                    "call_id": "call_2",
                    "name": "get_translation_hint",
                    "arguments": {"term": "the bill please"},
                },
                {"type": "session.ended"},
            ]
        )

        async def fake_call_dictionary_tool(self, term):
            return "die Rechnung bitte"

        monkeypatch.setattr(AssemblyAIRelay, "_call_dictionary_tool", fake_call_dictionary_tool)

        events = [event async for event in relay.events()]

        assert {
            "type": "hint",
            "term": "the bill please",
            "translation": "die Rechnung bitte",
            "level": 3,
        } in events
    finally:
        get_settings.cache_clear()


async def test_connect_sends_the_hint_tool_definition(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ASSEMBLYAI_API_KEY", "some-key")
    get_settings.cache_clear()
    try:
        scenario = ScenarioLoader().get("order_food")
        relay = AssemblyAIRelay(scenario)

        fake_ws = _FakeWebSocket([])

        async def fake_connect(*args, **kwargs):
            return fake_ws

        monkeypatch.setattr("app.services.voice_agent.assemblyai_client.websockets.connect", fake_connect)

        await relay.connect()

        session_update = next(m for m in fake_ws.sent if m["type"] == "session.update")
        # "output" (voice) can only ever be set on this very first
        # session.update — AssemblyAI rejects it on any later one.
        assert session_update["session"]["output"] == {"voice": relay._settings.assemblyai_voice_id}
        tools = session_update["session"]["tools"]
        tool_names = [t["name"] for t in tools]
        assert "get_translation_hint" in tool_names

        hint_tool = next(t for t in tools if t["name"] == "get_translation_hint")
        # Only "term" is required — a second required param (hint_level) was
        # tried and found live to make the model skip calling the tool
        # entirely far more often; see the comment on _HINT_TOOLS.
        assert hint_tool["parameters"]["required"] == ["term"]
    finally:
        get_settings.cache_clear()


async def test_send_user_text_folds_text_into_prompt_and_forces_a_reply(monkeypatch: pytest.MonkeyPatch):
    """There is no AssemblyAI message type for injecting text as if it were
    spoken — confirmed against the real API's documented client messages
    (session.update, session.resume, session.end, input.audio, tool.result,
    reply.create). send_user_text works around this via session.update
    (folding the typed text into a one-time directive) plus an explicit
    reply.create, since nothing else will trigger a reply for typed
    (non-audio) input."""
    monkeypatch.setenv("ASSEMBLYAI_API_KEY", "some-key")
    get_settings.cache_clear()
    try:
        scenario = ScenarioLoader().get("order_food")
        relay = AssemblyAIRelay(scenario)
        relay._ws = _FakeWebSocket([])
        relay._base_system_prompt = "BASE PROMPT"

        await relay.send_user_text("I would like a coffee")

        session_update = next(m for m in relay._ws.sent if m["type"] == "session.update")
        assert "BASE PROMPT" in session_update["session"]["system_prompt"]
        assert "I would like a coffee" in session_update["session"]["system_prompt"]
        # tools must be carried through, not dropped, by a mid-session update.
        assert any(t["name"] == "get_translation_hint" for t in session_update["session"]["tools"])
        # "output" must NOT be resent past the first session.update — confirmed
        # live that AssemblyAI rejects that with a session.error, even with an
        # unchanged voice value ("output.voice cannot be changed after the
        # first session.update").
        assert "output" not in session_update["session"]

        assert any(m["type"] == "reply.create" for m in relay._ws.sent)
        assert relay._pending_prompt_revert is True
    finally:
        get_settings.cache_clear()


async def test_inject_complication_folds_directive_into_prompt_without_forcing_a_reply(
    monkeypatch: pytest.MonkeyPatch,
):
    """Same session.update-based workaround as send_user_text, but
    deliberately does NOT send reply.create — that would race AssemblyAI's
    own auto-generated reply to the learner's just-finished turn (see the
    docstring on inject_complication)."""
    monkeypatch.setenv("ASSEMBLYAI_API_KEY", "some-key")
    get_settings.cache_clear()
    try:
        scenario = ScenarioLoader().get("order_food")
        relay = AssemblyAIRelay(scenario)
        relay._ws = _FakeWebSocket([])
        relay._base_system_prompt = "BASE PROMPT"

        await relay.inject_complication("The item is sold out")

        session_update = next(m for m in relay._ws.sent if m["type"] == "session.update")
        assert "BASE PROMPT" in session_update["session"]["system_prompt"]
        assert "The item is sold out" in session_update["session"]["system_prompt"]
        assert "output" not in session_update["session"]

        assert not any(m["type"] == "reply.create" for m in relay._ws.sent)
        assert relay._pending_prompt_revert is True
    finally:
        get_settings.cache_clear()


async def test_reply_done_reverts_the_system_prompt_after_a_pending_override(monkeypatch: pytest.MonkeyPatch):
    """The one-time directive from inject_complication/send_user_text must
    not linger into later turns — the next reply.done after either of them
    puts the base prompt back."""
    monkeypatch.setenv("ASSEMBLYAI_API_KEY", "some-key")
    get_settings.cache_clear()
    try:
        scenario = ScenarioLoader().get("order_food")
        relay = AssemblyAIRelay(scenario)
        relay._base_system_prompt = "BASE PROMPT"
        relay._ws = _FakeWebSocket([{"type": "reply.done", "status": "completed"}, {"type": "session.ended"}])
        relay._pending_prompt_revert = True

        [_ async for _ in relay.events()]

        assert relay._pending_prompt_revert is False
        session_updates = [m for m in relay._ws.sent if m["type"] == "session.update"]
        assert len(session_updates) == 1
        assert session_updates[0]["session"]["system_prompt"] == "BASE PROMPT"
        assert "output" not in session_updates[0]["session"]
    finally:
        get_settings.cache_clear()


async def test_reply_done_is_a_noop_when_no_override_is_pending(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ASSEMBLYAI_API_KEY", "some-key")
    get_settings.cache_clear()
    try:
        scenario = ScenarioLoader().get("order_food")
        relay = AssemblyAIRelay(scenario)
        relay._base_system_prompt = "BASE PROMPT"
        relay._ws = _FakeWebSocket([{"type": "reply.done", "status": "completed"}, {"type": "session.ended"}])
        relay._pending_prompt_revert = False

        [_ async for _ in relay.events()]

        assert not any(m["type"] == "session.update" for m in relay._ws.sent)
    finally:
        get_settings.cache_clear()
