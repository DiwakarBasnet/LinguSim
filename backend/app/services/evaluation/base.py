from abc import ABC, abstractmethod

from app.models.conversation import Transcript
from app.models.evaluation import EvaluationResult
from app.models.scenario import Scenario


class Evaluator(ABC):
    """Turns a finished session's transcript into structured feedback."""

    @abstractmethod
    async def evaluate(self, scenario: Scenario, transcript: Transcript) -> EvaluationResult:
        raise NotImplementedError
