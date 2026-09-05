import os
import tempfile

os.environ.setdefault("VOICE_AGENT_PROVIDER", "mock")
os.environ.setdefault("EVALUATION_PROVIDER", "mock")

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.db.session import get_engine
from app.main import app


@pytest.fixture
def client() -> TestClient:
    # Fresh sqlite file per test — tests must never share DB state or touch
    # a real Postgres instance.
    os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mktemp(suffix='.db')}"
    get_settings.cache_clear()
    get_engine.cache_clear()
    with TestClient(app) as test_client:
        yield test_client
