from app.db.models import LearnerProfileRecord
from app.models.evaluation import EvaluationResult
from app.models.scenario import Scenario
from app.services.profile_service import weakest_theme

DIFFICULTY_ORDER = ["beginner", "intermediate", "advanced"]

STRUGGLING_THRESHOLD = 50
EXCELLING_THRESHOLD = 80
RECOVERY_WEAK_THRESHOLD = 0.5


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
    otherwise holds. Among what's left, prefers whichever candidate touches
    the learner's single weakest tracked theme (a weak past-tense score
    visibly steers toward a scenario built around past tense next); if
    communication recovery is trending weak, further prefers scenarios with
    more possible_events — i.e. more complications to practice recovering
    from, since that's specifically the skill that needs more reps. Always
    stays within the language just practiced — recommending an English
    scenario after a German session would undercut the whole point of
    picking a language.
    """
    same_language = [s for s in all_scenarios if s.target_language == just_played.target_language]
    target_difficulty = _target_difficulty(just_played.difficulty, evaluation.overall_score)

    candidates = [s for s in same_language if s.difficulty == target_difficulty and s.id != just_played.id]
    if not candidates:
        candidates = [s for s in same_language if s.id != just_played.id] or same_language

    weak_theme = weakest_theme(profile)
    if weak_theme:
        themed = [s for s in candidates if weak_theme in s.grammar_themes or weak_theme in s.vocabulary_themes]
        if themed:
            candidates = themed

    if profile.communication_recovery is not None and profile.communication_recovery < RECOVERY_WEAK_THRESHOLD:
        candidates = sorted(candidates, key=lambda s: len(s.possible_events), reverse=True)

    return candidates[0]
