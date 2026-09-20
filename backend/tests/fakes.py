"""Test-only doubles for the real AssemblyAI-backed services. Not part of
the app — LinguSim itself has no mock mode; these exist purely so the test
suite never calls the real network (per the "never call the real API in
unit tests" requirement)."""

from collections.abc import AsyncIterator
from typing import Any

from app.db.models import LearnerProfileRecord
from app.models.conversation import Transcript
from app.models.evaluation import EvaluationResult
from app.models.scenario import Scenario


class FakeRelay:
    """Stands in for AssemblyAIRelay: same public shape, no network."""

    def __init__(self, scenario: Scenario, hint_language: str = "English"):
        self.scenario = scenario
        self.hint_language = hint_language

    async def connect(self) -> None:
        return None

    async def send_audio_chunk(self, pcm16_bytes: bytes) -> None:
        return None

    async def send_user_text(self, text: str) -> None:
        return None

    async def inject_complication(self, description: str) -> None:
        return None

    async def events(self) -> AsyncIterator[dict[str, Any]]:
        yield {"type": "agent_text", "text": f"({self.scenario.ai_role}) Hello!"}

    async def end(self) -> None:
        return None

    async def close(self) -> None:
        return None


class FakeEvaluator:
    """Stands in for LLMGatewayEvaluator: fixed, valid EvaluationResult, no network."""

    async def evaluate(
        self,
        scenario: Scenario,
        transcript: Transcript,
        complications: list[str] | None = None,
        learner_profile: LearnerProfileRecord | None = None,
        scenario_bank: list[Scenario] | None = None,
    ) -> EvaluationResult:
        return EvaluationResult(
            overall_score=70,
            grammar=70,
            vocabulary=70,
            fluency=70,
            hesitation=70,
            task_completion=70,
            conversation_handling=70,
            communication_recovery=70,
            weaknesses=[],
            strengths=[],
        )
