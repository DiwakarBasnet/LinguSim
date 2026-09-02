import logging

from app.models.conversation import Transcript
from app.models.scenario import Scenario
from app.services.voice_agent import create_voice_agent_session

logger = logging.getLogger(__name__)


class ConversationManager:
    """Owns one live scenario session: the voice agent, and the transcript being built."""

    def __init__(self, scenario: Scenario, provider: str):
        self.scenario = scenario
        self._session = create_voice_agent_session(provider, scenario)
        self.transcript = Transcript(scenario_id=scenario.id)

    async def start(self) -> str:
        opening_line = await self._session.start()
        self.transcript.add("ai", opening_line)
        return opening_line

    async def handle_learner_text(self, text: str) -> str:
        self.transcript.add("learner", text)
        reply = await self._session.respond(text)
        self.transcript.add("ai", reply)
        return reply

    async def end(self) -> Transcript:
        await self._session.close()
        logger.info(
            "conversation_ended",
            extra={"context": {"scenario_id": self.scenario.id, "turns": len(self.transcript.turns)}},
        )
        return self.transcript
