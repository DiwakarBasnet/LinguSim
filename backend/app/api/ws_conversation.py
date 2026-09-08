import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.db.session import create_session
from app.models.conversation import Transcript, Turn
from app.models.scenario import Scenario
from app.services.evaluation import LLMGatewayEvaluator
from app.services.scenario_loader import ScenarioNotFoundError, get_scenario_loader
from app.services.session_service import SessionService
from app.services.voice_agent import AssemblyAIRelay, AssemblyAIRelayError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["conversation"])

# Trigger one new complication every this-many learner turns, up to however
# many the scenario defines (see maybe_inject_complication below).
COMPLICATION_TURN_INTERVAL = 2


@router.websocket("/ws/conversation")
async def conversation_ws(websocket: WebSocket) -> None:
    """
    Text + binary protocol, backed by AssemblyAI's Voice Agent API — one
    managed session streaming raw PCM16 mono @ 24kHz audio in both
    directions alongside JSON transcript/control events.

    client -> server:
      {"type": "start", "scenario_id": "order_food"}
      {"type": "user_text", "text": "..."}      # typed fallback
      {"type": "end"}
      <binary PCM16 24kHz mono frame>            # mic audio

    server -> client:
      {"type": "session_ready"}
      {"type": "agent_text", "text": "...", "turn_index": N}
      {"type": "user_transcript", "text": "...", "turn_index": N}
      {"type": "clear_audio"}                    # barge-in: stop playback
      {"type": "complication", "text": "..."}     # a scripted complication just fired
      {"type": "session_end", "transcript": {...}, "evaluation": {...},
       "profile": {...}, "recommended_scenario_id": "..."}
      {"type": "error", "message": "..."}
      <binary PCM16 24kHz mono frame>            # agent reply audio
    """
    await websocket.accept()
    loader = get_scenario_loader()

    relay: AssemblyAIRelay | None = None
    relay_task: asyncio.Task | None = None
    scenario: Scenario | None = None
    turns: list[dict] = []
    complications_triggered: list[str] = []

    async def maybe_inject_complication() -> None:
        """
        What makes a simulation dynamic instead of a fixed script: every
        COMPLICATION_TURN_INTERVAL learner turns, actively push the next
        unused possible_events entry into the live conversation (see
        AssemblyAIRelay.inject_complication) rather than just hoping the
        model picks one up from the system prompt on its own.
        """
        assert scenario is not None and relay is not None
        if len(complications_triggered) >= len(scenario.possible_events):
            return
        learner_turns = sum(1 for t in turns if t["speaker"] == "learner")
        due = learner_turns // COMPLICATION_TURN_INTERVAL
        if due <= len(complications_triggered):
            return
        event = scenario.possible_events[len(complications_triggered)]
        complications_triggered.append(event)
        await relay.inject_complication(event)
        await websocket.send_json({"type": "complication", "text": event})

    async def pump_relay_events(active_relay: AssemblyAIRelay) -> None:
        try:
            async for event in active_relay.events():
                etype = event["type"]
                if etype in ("agent_text", "user_transcript"):
                    turn_index = len(turns)
                    speaker = "ai" if etype == "agent_text" else "learner"
                    turns.append({"turn_index": turn_index, "speaker": speaker, "text": event["text"]})
                    await websocket.send_json({"type": etype, "text": event["text"], "turn_index": turn_index})
                    if speaker == "learner":
                        await maybe_inject_complication()
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

    async def finish_and_report() -> None:
        assert scenario is not None
        transcript = Transcript(scenario_id=scenario.id, turns=[Turn(**t) for t in turns])
        db = create_session()
        try:
            service = SessionService(db, LLMGatewayEvaluator(), loader)
            result = await service.finish_session(scenario, transcript, complications_triggered)
        except Exception:
            logger.exception("session_finish_failed")
            await websocket.send_json(
                {"type": "session_end", "transcript": transcript.model_dump(), "error": "Evaluation failed."}
            )
            return
        finally:
            db.close()
        await websocket.send_json({"type": "session_end", "transcript": transcript.model_dump(), **result})

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

                try:
                    relay = AssemblyAIRelay(scenario)
                    await relay.connect()
                except AssemblyAIRelayError as exc:
                    await websocket.send_json({"type": "error", "message": str(exc)})
                    relay = None
                    scenario = None
                    continue
                await websocket.send_json({"type": "session_ready"})
                relay_task = asyncio.create_task(pump_relay_events(relay))

            elif msg_type == "user_text":
                text = message.get("text", "")
                if relay is None:
                    await websocket.send_json(
                        {"type": "error", "message": "Send a 'start' message before 'user_text'."}
                    )
                    continue
                turn_index = len(turns)
                turns.append({"turn_index": turn_index, "speaker": "learner", "text": text})
                # Inject any due complication into context BEFORE the reply
                # this triggers, so the one reply it generates can naturally
                # work it in, rather than racing a second reply against it.
                await maybe_inject_complication()
                await relay.send_user_text(text)

            elif msg_type == "end":
                if scenario is None or relay is None:
                    await websocket.send_json({"type": "session_end", "transcript": {"scenario_id": None, "turns": []}})
                    break
                await relay.end()
                if relay_task is not None:
                    try:
                        await asyncio.wait_for(relay_task, timeout=5)
                    except (TimeoutError, asyncio.CancelledError):
                        pass
                await relay.close()
                await finish_and_report()
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
        # Without an explicit close, the connection is simply abandoned once
        # this handler returns — no WebSocket close frame is ever sent, and
        # browsers surface that as a connection error even though session_end
        # already arrived successfully.
        try:
            await websocket.close()
        except Exception:
            pass
