from fastapi.testclient import TestClient

from app.config import get_settings


def test_health(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_list_scenarios(client: TestClient):
    resp = client.get("/scenarios")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert any(s["id"] == "order_food" for s in body)


def test_get_scenario_404(client: TestClient):
    resp = client.get("/scenarios/nope")
    assert resp.status_code == 404


def test_conversation_ws_full_flow(client: TestClient):
    with client.websocket_connect("/ws/conversation") as ws:
        ws.send_json({"type": "start", "scenario_id": "order_food"})
        ready = ws.receive_json()
        assert ready == {"type": "session_ready", "mode": "mock"}

        opening = ws.receive_json()
        assert opening["type"] == "agent_text"
        assert opening["turn_index"] == 0

        ws.send_json({"type": "user_text", "text": "Hi, I'd like a coffee please."})
        reply = ws.receive_json()
        assert reply["type"] == "agent_text"

        ws.send_json({"type": "end"})
        ended = ws.receive_json()
        assert ended["type"] == "session_end"
        transcript = ended["transcript"]
        assert transcript["scenario_id"] == "order_food"
        assert len(transcript["turns"]) == 3


def test_conversation_ws_unknown_scenario(client: TestClient):
    with client.websocket_connect("/ws/conversation") as ws:
        ws.send_json({"type": "start", "scenario_id": "nope"})
        resp = ws.receive_json()
        assert resp["type"] == "error"


def test_conversation_ws_user_text_before_start(client: TestClient):
    with client.websocket_connect("/ws/conversation") as ws:
        ws.send_json({"type": "user_text", "text": "hello"})
        resp = ws.receive_json()
        assert resp["type"] == "error"


def test_conversation_ws_assemblyai_without_api_key_errors(client: TestClient, monkeypatch):
    monkeypatch.setenv("VOICE_AGENT_PROVIDER", "assemblyai")
    monkeypatch.setenv("ASSEMBLYAI_API_KEY", "")
    get_settings.cache_clear()
    try:
        with client.websocket_connect("/ws/conversation") as ws:
            ws.send_json({"type": "start", "scenario_id": "order_food"})
            resp = ws.receive_json()
            assert resp["type"] == "error"
            assert "ASSEMBLYAI_API_KEY" in resp["message"]
    finally:
        get_settings.cache_clear()
