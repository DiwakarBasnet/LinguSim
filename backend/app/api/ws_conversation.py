import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import get_settings
from app.services.conversation_manager import ConversationManager
from app.services.scenario_loader import ScenarioNotFoundError, get_scenario_loader
from app.services.voice_agent.assemblyai_client import AssemblyAIRelay, AssemblyAIRelayError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["conversation"])


@router.websocket("/ws/conversation")
async def conversation_ws(websocket: WebSocket) -> None:
    """
    Text + binary protocol. The text (JSON) messages are the same regardless
    of provider; binary frames only apply to the "assemblyai" provider,
    which streams raw PCM16 mono @ 24kHz audio in both directions.

    client -> server:
      {"type": "start", "scenario_id": "order_food"}
      {"type": "user_text", "text": "..."}      # typed fallback, both providers
      {"type": "end"}
      <binary PCM16 24kHz mono frame>            # mic audio, assemblyai only

    server -> client:
      {"type": "session_ready", "mode": "mock" | "assemblyai"}
      {"type": "agent_text", "text": "...", "turn_index": N}
      {"type": "user_transcript", "text": "...", "turn_index": N}   # assemblyai only
      {"type": "clear_audio"}                    # assemblyai only: barge-in, stop playback
      {"type": "session_end", "transcript": {...}}
      {"type": "error", "message": "..."}
      <binary PCM16 24kHz mono frame>            # agent reply audio, assemblyai only
    """
    await websocket.accept()
    settings = get_settings()
    loader = get_scenario_loader()

    manager: ConversationManager | None = None
    relay: AssemblyAIRelay | None = None
    relay_task: asyncio.Task | None = None
    scenario_id: str | None = None
    relay_turns: list[dict] = []

    async def pump_relay_events(active_relay: AssemblyAIRelay) -> None:
        try:
            async for event in active_relay.events():
                etype = event["type"]
                if etype in ("agent_text", "user_transcript"):
                    turn_index = len(relay_turns)
                    speaker = "ai" if etype == "agent_text" else "learner"
                    relay_turns.append({"turn_index": turn_index, "speaker": speaker, "text": event["text"]})
                    await websocket.send_json({"type": etype, "text": event["text"], "turn_index": turn_index})
                elif etype == "agent_audio":
                    await websocket.send_bytes(event["data"])
                elif etype == "clear_audio":
                    await websocket.send_json({"type": "clear_audio"})
                elif etype == "error":
                    await websocket.send_json({"type": "error", "message": event["message"]})
                elif etype == "ended":
                    return
        except Exception:
            logger.exception("assemblyai_relay_pump_failed")
            try:
                await websocket.send_json({"type": "error", "message": "Voice agent connection failed."})
            except Exception:
                pass

    try:
        while True:
            raw_message = await websocket.receive()
            if raw_message["type"] == "websocket.disconnect":
                break

            if raw_message.get("bytes") is not None:
                if relay is not None:
                    await relay.send_audio_chunk(raw_message["bytes"])
                continue

            message = json.loads(raw_message["text"])
            msg_type = message.get("type")

            if msg_type == "start":
                scenario_id = message.get("scenario_id")
                try:
                    scenario = loader.get(scenario_id)
                except ScenarioNotFoundError:
                    await websocket.send_json(
                        {"type": "error", "message": f"Unknown scenario_id '{scenario_id}'"}
                    )
                    continue

                if settings.voice_agent_provider == "assemblyai":
                    try:
                        relay = AssemblyAIRelay(scenario)
                        await relay.connect()
                    except AssemblyAIRelayError as exc:
                        await websocket.send_json({"type": "error", "message": str(exc)})
                        relay = None
                        continue
                    await websocket.send_json({"type": "session_ready", "mode": "assemblyai"})
                    relay_task = asyncio.create_task(pump_relay_events(relay))
                else:
                    manager = ConversationManager(scenario, provider=settings.voice_agent_provider)
                    await websocket.send_json({"type": "session_ready", "mode": "mock"})
                    opening_line = await manager.start()
                    await websocket.send_json({"type": "agent_text", "text": opening_line, "turn_index": 0})

            elif msg_type == "user_text":
                text = message.get("text", "")
                if relay is not None:
                    turn_index = len(relay_turns)
                    relay_turns.append({"turn_index": turn_index, "speaker": "learner", "text": text})
                    await relay.send_user_text(text)
                elif manager is not None:
                    reply = await manager.handle_learner_text(text)
                    await websocket.send_json(
                        {"type": "agent_text", "text": reply, "turn_index": len(manager.transcript.turns) - 1}
                    )
                else:
                    await websocket.send_json(
                        {"type": "error", "message": "Send a 'start' message before 'user_text'."}
                    )

            elif msg_type == "end":
                if relay is not None:
                    await relay.end()
                    if relay_task is not None:
                        try:
                            await asyncio.wait_for(relay_task, timeout=5)
                        except (TimeoutError, asyncio.CancelledError):
                            pass
                    await relay.close()
                    await websocket.send_json(
                        {"type": "session_end", "transcript": {"scenario_id": scenario_id, "turns": relay_turns}}
                    )
                elif manager is not None:
                    transcript = await manager.end()
                    await websocket.send_json({"type": "session_end", "transcript": transcript.model_dump()})
                break

            else:
                await websocket.send_json({"type": "error", "message": f"Unknown message type '{msg_type}'"})

    except WebSocketDisconnect:
        logger.info("conversation_ws_disconnected")
    finally:
        if relay_task is not None and not relay_task.done():
            relay_task.cancel()
        if relay is not None:
            await relay.close()
