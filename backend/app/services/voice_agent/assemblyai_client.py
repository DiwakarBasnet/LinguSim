from app.config import get_settings
from app.services.voice_agent.base import VoiceAgentSession


class AssemblyAIVoiceAgentSession(VoiceAgentSession):
    """
    Real conversation partner backed by AssemblyAI's Voice Agent API
    (streaming STT + LLM + TTS in one managed session).

    NOT YET IMPLEMENTED. This is a placeholder that preserves the
    VoiceAgentSession interface so the rest of the app (WebSocket handler,
    conversation manager, frontend) needs zero changes once this is wired up.

    To implement:
      1. Set ASSEMBLYAI_API_KEY in .env and VOICE_AGENT_PROVIDER=assemblyai.
      2. Open an AssemblyAI Voice Agent session using the current API/SDK
         (check AssemblyAI's docs for the exact session-config and
         message-schema, since this evolves) and pass scenario.system_prompt()
         as the agent's instructions/context.
      3. In start()/respond(), forward audio in and yield the agent's spoken
         reply (and its text) back out — the ws_conversation handler already
         expects an async text-in/text-out shape per VoiceAgentSession, so
         only this class and the audio bridging in ws_conversation.py need
         to change, not the frontend contract.
    """

    def __init__(self, scenario):
        super().__init__(scenario)
        settings = get_settings()
        if not settings.assemblyai_api_key:
            raise RuntimeError(
                "ASSEMBLYAI_API_KEY is not set. Add it to .env before using "
                "VOICE_AGENT_PROVIDER=assemblyai."
            )

    async def start(self) -> str:
        raise NotImplementedError(
            "AssemblyAI Voice Agent integration is not implemented yet. "
            "Use VOICE_AGENT_PROVIDER=mock for now."
        )

    async def respond(self, learner_text: str) -> str:
        raise NotImplementedError(
            "AssemblyAI Voice Agent integration is not implemented yet. "
            "Use VOICE_AGENT_PROVIDER=mock for now."
        )
