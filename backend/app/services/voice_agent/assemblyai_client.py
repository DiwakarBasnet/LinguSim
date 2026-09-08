import base64
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import websockets
from websockets.asyncio.client import ClientConnection

from app.config import get_settings
from app.models.scenario import Scenario

logger = logging.getLogger(__name__)


class AssemblyAIRelayError(RuntimeError):
    pass


class AssemblyAIRelay:
    """
    Duplex bridge to AssemblyAI's managed Voice Agent API
    (wss://agents.assemblyai.com/v1/ws): one WebSocket session that handles
    STT, LLM, and TTS together — PCM16 mono @ 24kHz audio in, PCM16 mono @
    24kHz audio (+ transcript events) back out.

    This is deliberately not a call/response interface: AssemblyAI owns
    turn detection and barge-in itself and pushes events on its own
    schedule. ws_conversation.py drives this class directly,
    relaying audio bytes and forwarding normalized events to the browser.
    """

    def __init__(self, scenario: Scenario):
        self.scenario = scenario
        settings = get_settings()
        if not settings.assemblyai_api_key:
            raise AssemblyAIRelayError("ASSEMBLYAI_API_KEY is not set. Add it to .env to run LinguSim.")
        self._settings = settings
        self._ws: ClientConnection | None = None

    async def connect(self) -> None:
        self._ws = await websockets.connect(
            self._settings.assemblyai_ws_url,
            additional_headers={"Authorization": f"Bearer {self._settings.assemblyai_api_key}"},
        )
        await self._ws.send(
            json.dumps(
                {
                    "type": "session.update",
                    "session": {
                        "system_prompt": self.scenario.system_prompt(),
                        "output": {"voice": self._settings.assemblyai_voice_id},
                    },
                }
            )
        )
        # No scripted "greeting" text: the scenario's objectives/success
        # criteria are learner-facing instructions, not AI dialogue, and are
        # already written in the scenario's own target_language — hardcoding
        # any English framing around them would produce mixed-language
        # speech for non-English scenarios. Instead, let the model open
        # in character, in whatever language its system_prompt specifies.
        await self._ws.send(
            json.dumps({"type": "reply.create", "instructions": "Open the conversation, in character."})
        )
        logger.info("assemblyai_session_started", extra={"context": {"scenario_id": self.scenario.id}})

    async def send_audio_chunk(self, pcm16_bytes: bytes) -> None:
        if self._ws is None:
            return
        await self._ws.send(
            json.dumps({"type": "input.audio", "audio": base64.b64encode(pcm16_bytes).decode()})
        )

    async def send_user_text(self, text: str) -> None:
        """Fallback path for typed input (when a browser has no mic access)."""
        if self._ws is None:
            return
        await self._ws.send(json.dumps({"type": "conversation.message", "role": "user", "content": text}))
        await self._ws.send(json.dumps({"type": "reply.create"}))

    async def inject_complication(self, description: str) -> None:
        """
        Makes the simulation dynamic: pushes a system-level directive mid-
        conversation (not attributed to the learner) so the AI actively
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
        that entirely, at the cost of it occasionally landing one turn
        later than the trigger — an acceptable trade for a hackathon-scale
        feature.
        """
        if self._ws is None:
            return
        await self._ws.send(
            json.dumps(
                {
                    "type": "conversation.message",
                    "role": "system",
                    "content": f"Complication to introduce naturally in your next reply, in character: {description}",
                }
            )
        )

    async def events(self) -> AsyncIterator[dict[str, Any]]:
        """
        Normalizes AssemblyAI's event stream into the small vocabulary
        ws_conversation.py forwards to the browser: agent_text,
        user_transcript, agent_audio, clear_audio (barge-in), error, ended.
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
            elif etype == "session.error":
                yield {"type": "error", "message": event.get("message", "AssemblyAI session error")}
            elif etype == "session.ended":
                yield {"type": "ended"}
                return
            # session.ready / session.updated / reply.started / reply.done /
            # *.delta / tool.* are not needed for this MVP's UI.

    async def end(self) -> None:
        if self._ws is None:
            return
        try:
            await self._ws.send(json.dumps({"type": "session.end"}))
        except Exception:
            logger.warning("assemblyai_end_send_failed", exc_info=True)

    async def close(self) -> None:
        if self._ws is not None:
            await self._ws.close()
            self._ws = None
