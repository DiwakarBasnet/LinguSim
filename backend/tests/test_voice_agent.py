import pytest

from app.config import get_settings
from app.services.scenario_loader import ScenarioLoader
from app.services.voice_agent import AssemblyAIRelay, AssemblyAIRelayError


def test_relay_requires_an_api_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ASSEMBLYAI_API_KEY", "")
    get_settings.cache_clear()
    try:
        scenario = ScenarioLoader().get("order_food")
        with pytest.raises(AssemblyAIRelayError, match="ASSEMBLYAI_API_KEY"):
            AssemblyAIRelay(scenario)
    finally:
        get_settings.cache_clear()
