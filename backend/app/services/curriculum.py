from app.db.models import LearnerProfileRecord
from app.models.evaluation import EvaluationResult
from app.models.scenario import Scenario
from app.services.profile_service import weakest_theme

DIFFICULTY_ORDER = ["beginner", "intermediate", "advanced"]

STRUGGLING_THRESHOLD = 50
EXCELLING_THRESHOLD = 80


def _target_difficulty(current: str, overall_score: int) -> str:
    idx = DIFFICULTY_ORDER.index(current)
    if overall_score >= EXCELLING_THRESHOLD and idx < len(DIFFICULTY_ORDER) - 1:
        return DIFFICULTY_ORDER[idx + 1]
    if overall_score < STRUGGLING_THRESHOLD and idx > 0:
        return DIFFICULTY_ORDER[idx - 1]
    return current


def recommend_next_scenario(
    profile: LearnerProfileRecord,
    evaluation: EvaluationResult,
    just_played: Scenario,
    all_scenarios: list[Scenario],
) -> Scenario:
    """
    Difficulty rises after a strong session, falls after a weak one, and
    otherwise holds — then prefers whichever candidate scenario touches the
    learner's single weakest tracked theme, so a weak past-tense score can
    visibly steer toward a scenario built around past tense next.
    """
    target_difficulty = _target_difficulty(just_played.difficulty, evaluation.overall_score)

    candidates = [s for s in all_scenarios if s.difficulty == target_difficulty and s.id != just_played.id]
    if not candidates:
        candidates = [s for s in all_scenarios if s.id != just_played.id] or list(all_scenarios)

    weak_theme = weakest_theme(profile)
    if weak_theme:
        themed = [s for s in candidates if weak_theme in s.grammar_themes or weak_theme in s.vocabulary_themes]
        if themed:
            return themed[0]

    return candidates[0]
