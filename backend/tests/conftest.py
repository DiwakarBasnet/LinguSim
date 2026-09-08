import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.db.session import get_engine
from app.main import app
from tests.fakes import FakeEvaluator, FakeRelay


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    # Fresh sqlite file per test — tests must never share DB state or touch
    # a real Postgres instance.
    os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mktemp(suffix='.db')}"
    get_settings.cache_clear()
    get_engine.cache_clear()

    # LinguSim has no mock mode of its own — these test doubles replace the
    # real AssemblyAI-backed classes at the call site so the suite never
    # touches the real network.
    monkeypatch.setattr("app.api.ws_conversation.AssemblyAIRelay", FakeRelay)
    monkeypatch.setattr("app.api.ws_conversation.LLMGatewayEvaluator", FakeEvaluator)

    with TestClient(app) as test_client:
        yield test_client
