from sqlalchemy.orm import Session

from app.db.models import LearnerProfileRecord
from app.models.evaluation import EvaluationResult
from app.models.scenario import Scenario

# No auth/multi-user support in this MVP — one implicit learner.
DEFAULT_PROFILE_ID = "default"
EMA_ALPHA = 0.3


def _ema(old: float | None, new_signal: float) -> float:
    if old is None:
        return new_signal
    return old + EMA_ALPHA * (new_signal - old)


def get_or_create_profile(db: Session, target_language: str = "English") -> LearnerProfileRecord:
    profile = db.get(LearnerProfileRecord, DEFAULT_PROFILE_ID)
    if profile is None:
        profile = LearnerProfileRecord(id=DEFAULT_PROFILE_ID, target_language=target_language)
        db.add(profile)
        db.flush()
    return profile


def update_profile_from_evaluation(
    db: Session,
    profile: LearnerProfileRecord,
    scenario: Scenario,
    evaluation: EvaluationResult,
) -> LearnerProfileRecord:
    """
    Applies one session's evaluation to the profile via exponential moving
    average, keyed by the scenario's own grammar/vocabulary themes. The
    evaluator only ever returns one grammar/vocabulary score for the whole
    session (not per-theme), so that single signal is applied to every theme
    the scenario touched — a reasonable approximation without inventing
    per-theme scores the evaluator never produced.
    """
    grammar_signal = evaluation.grammar / 100
    grammar = dict(profile.grammar)
    for theme in scenario.grammar_themes:
        grammar[theme] = _ema(grammar.get(theme), grammar_signal)
    profile.grammar = grammar

    vocabulary_signal = evaluation.vocabulary / 100
    vocabulary = dict(profile.vocabulary)
    for theme in scenario.vocabulary_themes:
        vocabulary[theme] = _ema(vocabulary.get(theme), vocabulary_signal)
    profile.vocabulary = vocabulary

    profile.fluency = _ema(profile.fluency, evaluation.fluency / 100)
    profile.hesitation = _ema(profile.hesitation, evaluation.hesitation / 100)
    profile.completed_scenarios += 1
    profile.target_language = scenario.target_language
    # pronunciation is never set here — see LearnerProfileRecord docstring.

    db.add(profile)
    db.flush()
    return profile


def weakest_theme(profile: LearnerProfileRecord) -> str | None:
    combined = {**profile.grammar, **profile.vocabulary}
    if not combined:
        return None
    return min(combined, key=combined.get)


def profile_to_dict(profile: LearnerProfileRecord) -> dict:
    return {
        "target_language": profile.target_language,
        "level": profile.level,
        "grammar": profile.grammar,
        "vocabulary": profile.vocabulary,
        "fluency": profile.fluency,
        "hesitation": profile.hesitation,
        "pronunciation": None,  # not assessed — see LearnerProfileRecord docstring
        "completed_scenarios": profile.completed_scenarios,
        "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
    }
