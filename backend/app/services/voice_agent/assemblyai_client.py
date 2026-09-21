import base64
import json
import logging
import mcp
import websockets
from websockets.asyncio.client import ClientConnection
from collections.abc import AsyncIterator
from typing import Any

from app.config import get_settings
from app.models.scenario import Scenario
from app.services.dictionary_mcp import dictionary_server

logger = logging.getLogger(__name__)

_HINT_TOOL_NAME = "get_translation_hint"
_GRAMMAR_TOOL_NAME = "flag_grammar_correction"
_HINT_TOOLS = [
    {
        "type": "function",
        "name": _HINT_TOOL_NAME,
        "description": (
            "Look up a real translation for a word or short phrase the learner is stuck on or didn't understand, "
            "so a hint can be grounded in an actual translation instead of a guess. Only call "
            "this for hints (Level 2, Level 3, or Comprehension hints), per the hint "
            "system in your instructions — never proactively."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "term": {
                    "type": "string",
                    "description": (
                        "The word or short phrase to translate."
                    ),
                },
                "direction": {
                    "type": "string",
                    "enum": ["into_target", "into_hint"],
                    "description": (
                        "Translate 'into_target' (from Hint Language to Target Language) if the learner doesn't know how to say something. "
                        "Translate 'into_hint' (from Target Language to Hint Language) if the learner didn't understand what you said."
                    )
                },
            },
            "required": ["term", "direction"],
        },
        "execution_mode": "interactive",
        "timeout_seconds": 8,
    },
    {
        "type": "function",
        "name": _GRAMMAR_TOOL_NAME,
        "description": (
            "Silently flag a grammar mistake the learner just made, per the grammar-correction "
            "rules in your instructions. This never gets spoken aloud — it only surfaces to the "
            "learner as a written note, so it never interrupts the conversation."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "note": {
                    "type": "string",
                    "description": (
                        "A short correction, written entirely in the learner's chosen hint "
                        "language: what was wrong and the corrected form."
                    ),
                },
            },
            "required": ["note"],
        },
        "execution_mode": "interactive",
        "timeout_seconds": 8,
    },
]


class AssemblyAIRelayError(RuntimeError):
    pass


class AssemblyAIRelay:
    """
    Duplex bridge to AssemblyAI's managed Voice Agent API that handles STT,
    LLM, and TTS together, so the server doesn't have to run its own LLM or TTS.
    """

    def __init__(self, scenario: Scenario, hint_language: str = "English"):
        self.scenario = scenario
        self.hint_language = hint_language
        settings = get_settings()
        if not settings.assemblyai_api_key:
            raise AssemblyAIRelayError("ASSEMBLYAI_API_KEY is not set. Add it to .env to run LinguSim.")
        self._settings = settings
        self._ws: ClientConnection | None = None
        self._base_system_prompt: str = ""
        self._pending_prompt_revert = False

    async def connect(self) -> None:
        """
        Raises AssemblyAIRelayError for any failure to reach - the caller can catch and
        turn into a friendly WebSocket error message, instead of an unhandled exception
        that would crash the whole conversation_ws handler mid-demo.
        """
        try:
            self._ws = await websockets.connect(
                self._settings.assemblyai_ws_url,
                additional_headers={"Authorization": f"Bearer {self._settings.assemblyai_api_key}"},
            )
            self._base_system_prompt = self.scenario.system_prompt(self.hint_language)
            await self._send_session_update(self._base_system_prompt, include_output=True)
            await self._ws.send(
                json.dumps({"type": "reply.create", "instructions": "Open the conversation, in character."})
            )
        except AssemblyAIRelayError:
            raise
        except Exception as exc:
            logger.exception("assemblyai_connect_failed", extra={"context": {"scenario_id": self.scenario.id}})
            raise AssemblyAIRelayError(
                "Couldn't connect to the voice agent. Check your network and ASSEMBLYAI_API_KEY, then try again."
            ) from exc
        logger.info("assemblyai_session_started", extra={"context": {"scenario_id": self.scenario.id}})

    async def _send_session_update(self, system_prompt: str, *, include_output: bool = False) -> None:
        """
        Sends session.update with the given system_prompt, repeating "tools"
        too so a mid-session update never silently drops get_translation_hint.
        Deliberately does NOT repeat "output" (voice) past the very first
        call in connect() — confirmed live that AssemblyAI rejects any later
        session.update that includes it at all, even with the same value,
        with a session.error: "'output.voice' cannot be changed after the
        first session.update".
        """
        if self._ws is None:
            return
        session: dict[str, Any] = {"system_prompt": system_prompt, "tools": _HINT_TOOLS}
        if include_output:
            session["output"] = {"voice": self._settings.assemblyai_voice_id}
        await self._ws.send(
            json.dumps(
                {
                    "type": "session.update",
                    "session": session,
                }
            )
        )

    async def send_audio_chunk(self, pcm16_bytes: bytes) -> None:
        if self._ws is None:
            return
        await self._ws.send(
            json.dumps({"type": "input.audio", "audio": base64.b64encode(pcm16_bytes).decode()})
        )

    async def send_user_text(self, text: str) -> None:
        """
        Fallback path for typed input (when a browser has no mic access).

        AssemblyAI's Voice Agent API has no message type for injecting text
        as if it had been spoken by the user — confirmed against the real
        API's documented client messages (session.update, session.resume,
        session.end, input.audio, tool.result, reply.create; there is no
        "conversation.message" or equivalent). The closest real lever is
        session.update: fold the typed text into the system prompt as a
        one-time directive, then force a reply with reply.create — there's
        no audio-driven turn to race here, since nothing was actually
        spoken, so an explicit reply.create is exactly what's needed.
        """
        if self._ws is None:
            return
        directive = (
            "The learner just typed the following as their turn — they did not speak it "
            f'aloud, but respond to it now, in character, as if they had said it: "{text}"'
        )
        await self._send_session_update(f"{self._base_system_prompt}\n\n{directive}")
        self._pending_prompt_revert = True
        await self._ws.send(json.dumps({"type": "reply.create"}))

    async def inject_complication(self, description: str) -> None:
        """
        Makes the simulation dynamic: folds a one-time directive into the
        system prompt (see send_user_text's docstring for why session.update
        is the only real lever available for this — there's no message type
        for injecting arbitrary conversation content) so the AI actively
        introduces a complication from the scenario's own possible_events
        into its next reply, in character — rather than just having been
        told about it once up front and maybe never using it. This is what
        turns a static scripted scenario into one that reacts to how far
        the conversation has gotten.

        Deliberately does NOT also send reply.create: AssemblyAI already
        auto-generates a reply after every learner turn on its own, and an
        explicit reply.create issued around the same moment races it —
        confirmed live, it produces two garbled, partially-overlapping
        replies instead of one that naturally works the complication in.
        Letting the already-pending/next natural reply pick this up avoids
        that entirely. Live testing found a consistent ~2 second gap
        between the learner's turn finishing and that natural reply
        starting, comfortably enough time for this session.update to land
        first and actually be picked up.
        """
        if self._ws is None:
            return
        directive = (
            "IMPORTANT: work this into your very next reply naturally, in character, then "
            f"don't mention it again unless it comes up naturally on its own: {description}"
        )
        await self._send_session_update(f"{self._base_system_prompt}\n\n{directive}")
        self._pending_prompt_revert = True

    async def events(self) -> AsyncIterator[dict[str, Any]]:
        """
        Normalizes AssemblyAI's event stream into the small vocabulary
        ws_conversation.py forwards to the browser: agent_text,
        user_transcript, agent_audio, clear_audio (barge-in), hint, error,
        ended.
        """
        if self._ws is None:
            return
        async for raw in self._ws:
            if isinstance(raw, bytes):
                continue
            event = json.loads(raw)
            etype = event.get("type")

            if etype == "transcript.agent":
                yield {"type": "agent_text", "text": event.get("text", "")}
            elif etype == "transcript.user":
                yield {"type": "user_transcript", "text": event.get("text", "")}
            elif etype == "reply.audio":
                yield {"type": "agent_audio", "data": base64.b64decode(event["data"])}
            elif etype == "input.speech.started":
                # The learner started talking — AssemblyAI will stop the
                # in-flight reply server-side; tell the browser to drop
                # whatever agent audio it already has queued for playback.
                yield {"type": "clear_audio"}
            elif etype == "tool.call":
                hint_event = await self._handle_tool_call(event)
                if hint_event is not None:
                    yield hint_event
            elif etype == "session.error":
                yield {"type": "error", "message": event.get("message", "AssemblyAI session error")}
            elif etype == "session.ended":
                yield {"type": "ended"}
                return
            elif etype == "reply.done" and self._pending_prompt_revert:
                # The reply that inject_complication/send_user_text's
                # one-time directive was aimed at has now finished (whether
                # completed or barge-in interrupted) — put the base prompt
                # back so the directive doesn't linger into later turns.
                self._pending_prompt_revert = False
                await self._send_session_update(self._base_system_prompt)
            # session.ready / session.updated / reply.started / other
            # reply.done / *.delta are not needed for this MVP's UI.

    async def _handle_tool_call(self, event: dict[str, Any]) -> dict[str, Any] | None:
        """
        Executes a tool.call from AssemblyAI and sends its tool.result back.
        Returns a normalized "hint"/"grammar_hint" event for the browser (so
        it's visible, not just inferred from the AI's next line), or None if
        the call was for an unknown tool.
        """
        call_id = event.get("call_id")
        name = event.get("name")
        arguments = event.get("arguments") or {}

        if name == _GRAMMAR_TOOL_NAME:
            note = str(arguments.get("note", ""))
            if self._ws is not None:
                await self._ws.send(
                    json.dumps({"type": "tool.result", "call_id": call_id, "result": json.dumps({"status": "ok"})})
                )
            return {"type": "grammar_hint", "note": note}

        if name != _HINT_TOOL_NAME:
            logger.warning("unknown_tool_call", extra={"context": {"name": name}})
            return None

        term = str(arguments.get("term", ""))
        direction = str(arguments.get("direction", "into_target"))
        
        if direction == "into_hint":
            src_lang = self.scenario.target_language
            tgt_lang = self.hint_language
        else:
            src_lang = self.hint_language
            tgt_lang = self.scenario.target_language

        translation = await self._call_dictionary_tool(term, src_lang, tgt_lang)

        if self._ws is not None:
            await self._ws.send(
                json.dumps({"type": "tool.result", "call_id": call_id, "result": json.dumps({"translation": translation})})
            )

        # There's no hint_level argument from the model (see the comment on
        # _HINT_TOOLS above for why) — a single word is a level-2 partial
        # hint, multiple words is a level-3 target phrase.
        hint_level = 3 if len(term.split()) > 1 else 2
        return {"type": "hint", "term": term, "translation": translation, "level": hint_level}

    async def _call_dictionary_tool(self, term: str, src_lang: str, tgt_lang: str) -> str:
        """Bridges to the real MCP server in dictionary_mcp.py — see that
        module's docstring for why this connects in-process rather than
        over a network. Translates between given languages."""
        try:
            async with mcp.Client(dictionary_server) as client:
                result = await client.call_tool(
                    "translate",
                    {
                        "term": term,
                        "source_language": src_lang,
                        "target_language": tgt_lang,
                    },
                )
        except Exception:
            logger.warning("dictionary_tool_call_failed", exc_info=True, extra={"context": {"term": term}})
            return f"Translation unavailable for '{term}'."

        if result.structured_content and "result" in result.structured_content:
            return str(result.structured_content["result"])
        if result.content:
            return str(result.content[0].text)
        return f"Translation unavailable for '{term}'."

    async def end(self) -> None:
        if self._ws is None:
            return
        try:
            await self._ws.send(json.dumps({"type": "session.end"}))
        except Exception:
            logger.warning("assemblyai_end_send_failed", exc_info=True)

    async def close(self) -> None:
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                logger.warning("assemblyai_close_failed", exc_info=True)
            finally:
                self._ws = None
