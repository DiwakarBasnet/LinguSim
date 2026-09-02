from app.models.scenario import Scenario
from app.services.voice_agent.base import VoiceAgentSession
from app.services.voice_agent.mock import MockVoiceAgentSession

__all__ = ["VoiceAgentSession", "MockVoiceAgentSession", "create_voice_agent_session"]


def create_voice_agent_session(provider: str, scenario: Scenario) -> VoiceAgentSession:
    """
    Builds a call/response VoiceAgentSession. Only "mock" fits this shape —
    the real AssemblyAI provider is a duplex audio relay (see
    app.services.voice_agent.assemblyai_client.AssemblyAIRelay) driven
    directly by app.api.ws_conversation, not through this factory.
    """
    if provider == "mock":
        return MockVoiceAgentSession(scenario=scenario)
    raise ValueError(f"Unsupported provider for create_voice_agent_session: {provider}")
