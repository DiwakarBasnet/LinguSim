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

        assert 0 <= ended["evaluation"]["overall_score"] <= 100
        assert ended["profile"]["completed_scenarios"] == 1
        assert ended["profile"]["pronunciation"] is None
        assert ended["recommended_scenario_id"] != "order_food"


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


def test_get_profile_before_any_session_is_a_blank_default(client: TestClient):
    resp = client.get("/profile")
    assert resp.status_code == 200
    body = resp.json()
    assert body["completed_scenarios"] == 0
    assert body["grammar"] == {}
    assert body["pronunciation"] is None


def test_sessions_list_empty_then_populated_after_a_completed_session(client: TestClient):
    assert client.get("/sessions").json() == []

    with client.websocket_connect("/ws/conversation") as ws:
        ws.send_json({"type": "start", "scenario_id": "order_food"})
        ws.receive_json()  # session_ready
        ws.receive_json()  # opening agent_text
        ws.send_json({"type": "end"})
        ws.receive_json()  # session_end

    sessions = client.get("/sessions").json()
    assert len(sessions) == 1
    assert sessions[0]["scenario_id"] == "order_food"
    assert sessions[0]["scenario_title"] == "Ordering Food at a Cafe"
    assert "overall_score" in sessions[0]["evaluation"]


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
