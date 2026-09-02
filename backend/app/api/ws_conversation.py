import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import get_settings
from app.services.conversation_manager import ConversationManager
from app.services.scenario_loader import ScenarioNotFoundError, get_scenario_loader

logger = logging.getLogger(__name__)

router = APIRouter(tags=["conversation"])


@router.websocket("/ws/conversation")
async def conversation_ws(websocket: WebSocket) -> None:
    """
    Minimal text-based protocol so the frontend contract stays stable
    whether the backend is driving the mock agent or the real AssemblyAI
    Voice Agent underneath:

    client -> server:
      {"type": "start", "scenario_id": "order_food"}
      {"type": "user_text", "text": "..."}
      {"type": "end"}

    server -> client:
      {"type": "agent_text", "text": "...", "turn_index": N}
      {"type": "session_end", "transcript": {...}}
      {"type": "error", "message": "..."}
    """
    await websocket.accept()
    settings = get_settings()
    loader = get_scenario_loader()
    manager: ConversationManager | None = None

    try:
        while True:
            message = await websocket.receive_json()
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
                manager = ConversationManager(scenario, provider=settings.voice_agent_provider)
                opening_line = await manager.start()
                await websocket.send_json(
                    {"type": "agent_text", "text": opening_line, "turn_index": 0}
                )

            elif msg_type == "user_text":
                if manager is None:
                    await websocket.send_json(
                        {"type": "error", "message": "Send a 'start' message before 'user_text'."}
                    )
                    continue
                reply = await manager.handle_learner_text(message.get("text", ""))
                await websocket.send_json(
                    {
                        "type": "agent_text",
                        "text": reply,
                        "turn_index": len(manager.transcript.turns) - 1,
                    }
                )

            elif msg_type == "end":
                if manager is not None:
                    transcript = await manager.end()
                    await websocket.send_json(
                        {"type": "session_end", "transcript": transcript.model_dump()}
                    )
                break

            else:
                await websocket.send_json({"type": "error", "message": f"Unknown message type '{msg_type}'"})

    except WebSocketDisconnect:
        logger.info("conversation_ws_disconnected")
