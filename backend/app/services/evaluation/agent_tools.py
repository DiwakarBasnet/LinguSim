"""
The four tools available to the evaluator agent (see llm_gateway.py). Each
one reuses an existing piece of the app rather than reimplementing
anything: read_transcript formats the same Transcript the rest of the app
already has, read_learner_profile/read_scenario_bank expose data the caller
already fetched, and propose_next_scenario calls the exact same
curriculum.recommend_next_scenario the app uses everywhere else — so the
agent's recommendation is grounded in the real scenario bank and profile,
not a guess, and the app's actual curriculum logic never gets duplicated.

All four are synchronous, local, and side-effect-free (no I/O, no
exceptions) — deliberately simple compared to the MCP-backed hint tool,
since there's no external grounding need here, just controlled access to
data the agent would otherwise have to be handed all at once.
"""

import json
from collections.abc import Callable

from app.db.models import LearnerProfileRecord
from app.models.conversation import Transcript
from app.models.evaluation import EvaluationResult
from app.models.scenario import Scenario
from app.services import curriculum, profile_service

ToolFn = Callable[..., str]


def _format_transcript(transcript: Transcript) -> str:
    lines = []
    for turn in transcript.turns:
        speaker = "Learner" if turn.speaker == "learner" else "AI"
        lines.append(f"{speaker}: {turn.text}")
    return "\n".join(lines) or "(empty transcript — the session ended before any turns)"


def build_tools(
    scenario: Scenario,
    transcript: Transcript,
    learner_profile: LearnerProfileRecord | None,
    scenario_bank: list[Scenario],
) -> dict[str, ToolFn]:
    def read_transcript(**_kwargs: object) -> str:
        return _format_transcript(transcript)

    def read_learner_profile(**_kwargs: object) -> str:
        if learner_profile is None:
            return "No prior profile data — this may be the learner's first session."
        return json.dumps(profile_service.profile_to_dict(learner_profile))

    def read_scenario_bank(**_kwargs: object) -> str:
        same_language = [s for s in scenario_bank if s.target_language == scenario.target_language]
        entries = [
            {
                "id": s.id,
                "title": s.title,
                "difficulty": s.difficulty,
                "grammar_themes": s.grammar_themes,
                "vocabulary_themes": s.vocabulary_themes,
                "possible_events_count": len(s.possible_events),
            }
            for s in same_language
        ]
        return json.dumps(entries)

    def propose_next_scenario(overall_score: object = 50, **_kwargs: object) -> str:
        if learner_profile is None or not scenario_bank:
            return "No profile/scenario data available — can't make a grounded recommendation."
        try:
            score = int(overall_score)  # the model may send it as a numeric string
        except (TypeError, ValueError):
            score = 50
        score = max(0, min(100, score))
        stub_evaluation = EvaluationResult(
            overall_score=score,
            grammar=score,
            vocabulary=score,
            fluency=score,
            hesitation=score,
            task_completion=score,
            conversation_handling=score,
            communication_recovery=score,
        )
        recommended = curriculum.recommend_next_scenario(learner_profile, stub_evaluation, scenario, scenario_bank)
        return (
            f"Recommended next scenario: '{recommended.title}' (id={recommended.id}, "
            f"difficulty={recommended.difficulty})."
        )

    return {
        "read_transcript": read_transcript,
        "read_learner_profile": read_learner_profile,
        "read_scenario_bank": read_scenario_bank,
        "propose_next_scenario": propose_next_scenario,
    }
