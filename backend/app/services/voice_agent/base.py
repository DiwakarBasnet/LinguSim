from abc import ABC, abstractmethod

from app.models.scenario import Scenario


class VoiceAgentSession(ABC):
    """
    Provider-agnostic interface for a single conversation-partner session.

    A conversation always flows as: start() once, then respond() for each
    learner turn, then close() when the scenario ends. Text in, text out —
    audio transport (mic capture, STT, TTS playback) is handled at the edges
    (browser + provider client), not here, so the conversation manager and
    the WebSocket protocol stay identical whether the provider is "mock" or
    "assemblyai".
    """

    def __init__(self, scenario: Scenario):
        self.scenario = scenario

    @abstractmethod
    async def start(self) -> str:
        """Return the AI's opening line for the scenario."""
        raise NotImplementedError

    @abstractmethod
    async def respond(self, learner_text: str) -> str:
        """Return the AI's reply to what the learner just said."""
        raise NotImplementedError

    async def close(self) -> None:
        """Release any provider resources. No-op by default."""
        return None
