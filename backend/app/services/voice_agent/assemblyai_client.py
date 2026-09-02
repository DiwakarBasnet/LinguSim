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

    This deliberately does NOT implement VoiceAgentSession: that interface
    is call/response per learner turn, which fits the rule-based mock, but
    AssemblyAI owns turn detection and barge-in itself and pushes events on
    its own schedule. ws_conversation.py drives this class directly,
    relaying audio bytes and forwarding normalized events to the browser.
    """

    def __init__(self, scenario: Scenario):
        self.scenario = scenario
        settings = get_settings()
        if not settings.assemblyai_api_key:
            raise AssemblyAIRelayError(
                "ASSEMBLYAI_API_KEY is not set. Add it to .env before using "
                "VOICE_AGENT_PROVIDER=assemblyai."
            )
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
                        "greeting": f"Hello! {self._opening_hint()}",
                        "output": {"voice": self._settings.assemblyai_voice_id},
                    },
                }
            )
        )
        logger.info("assemblyai_session_started", extra={"context": {"scenario_id": self.scenario.id}})

    def _opening_hint(self) -> str:
        if self.scenario.objectives:
            return self.scenario.objectives[0]
        return "Let's get started."

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
