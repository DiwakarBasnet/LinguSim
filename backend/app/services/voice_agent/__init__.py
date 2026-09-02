from app.models.scenario import Scenario
from app.services.voice_agent.base import VoiceAgentSession
from app.services.voice_agent.mock import MockVoiceAgentSession

__all__ = ["VoiceAgentSession", "MockVoiceAgentSession", "create_voice_agent_session"]


def create_voice_agent_session(provider: str, scenario: Scenario) -> VoiceAgentSession:
    if provider == "mock":
        return MockVoiceAgentSession(scenario=scenario)
    if provider == "assemblyai":
        from app.services.voice_agent.assemblyai_client import AssemblyAIVoiceAgentSession

        return AssemblyAIVoiceAgentSession(scenario=scenario)
    raise ValueError(f"Unknown voice agent provider: {provider}")
