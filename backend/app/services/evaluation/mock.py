import re

from app.models.conversation import Transcript
from app.models.evaluation import EvaluationResult
from app.models.scenario import Scenario
from app.services.evaluation.base import Evaluator

_FILLER_PATTERN = re.compile(r"\b(um+|uh+|erm+|like|you know)\b", re.IGNORECASE)


class MockEvaluator(Evaluator):
    """
    Zero-cost heuristic evaluator for offline dev/tests. Like
    MockVoiceAgentSession, this does NOT actually assess language quality —
    grammar/vocabulary/conversation_handling are computed from surface
    statistics (turn/word counts, filler words), not real understanding.
    Swap EVALUATION_PROVIDER to "llm_gateway" for a real assessment.
    """

    async def evaluate(self, scenario: Scenario, transcript: Transcript) -> EvaluationResult:
        learner_turns = [t.text for t in transcript.turns if t.speaker == "learner"]
        words = " ".join(learner_turns).split()
        total_words = len(words)
        unique_ratio = len(set(w.lower() for w in words)) / total_words if total_words else 0.0
        avg_words_per_turn = total_words / len(learner_turns) if learner_turns else 0.0
        filler_count = sum(len(_FILLER_PATTERN.findall(t)) for t in learner_turns)

        task_completion = _clamp(round(100 * len(learner_turns) / max(1, len(scenario.objectives))))
        conversation_handling = 70 if learner_turns else 30
        fluency = _clamp(round(avg_words_per_turn * 12))
        hesitation = _clamp(100 - filler_count * 15)
        vocabulary = _clamp(round(unique_ratio * 100))
        grammar = 60  # no real grammatical analysis without an LLM/NLP model

        overall = _clamp(round((task_completion + conversation_handling + fluency + hesitation + vocabulary + grammar) / 6))

        weaknesses = []
        if grammar < 70 and scenario.grammar_themes:
            weaknesses.append(scenario.grammar_themes[0])
        if vocabulary < 70 and scenario.vocabulary_themes:
            weaknesses.append(scenario.vocabulary_themes[0])

        strengths = []
        if task_completion >= 80:
            strengths.append("Completed the conversation's objectives")
        if vocabulary >= 70:
            strengths.append("Used varied vocabulary")

        return EvaluationResult(
            overall_score=overall,
            grammar=grammar,
            vocabulary=vocabulary,
            fluency=fluency,
            hesitation=hesitation,
            task_completion=task_completion,
            conversation_handling=conversation_handling,
            weaknesses=weaknesses,
            strengths=strengths,
        )


def _clamp(value: int) -> int:
    return max(0, min(100, value))
