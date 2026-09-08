import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import Base
from app.models.evaluation import EvaluationResult
from app.services import profile_service
from app.services.scenario_loader import ScenarioLoader


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def scenario():
    return ScenarioLoader().get("order_food")


def _evaluation(**overrides) -> EvaluationResult:
    defaults = dict(
        overall_score=70,
        grammar=80,
        vocabulary=60,
        fluency=75,
        hesitation=90,
        task_completion=100,
        conversation_handling=70,
        communication_recovery=65,
        weaknesses=[],
        strengths=[],
    )
    defaults.update(overrides)
    return EvaluationResult(**defaults)


def test_get_or_create_profile_creates_default(db):
    profile = profile_service.get_or_create_profile(db, "English")
    assert profile.id == profile_service.DEFAULT_PROFILE_ID
    assert profile.completed_scenarios == 0
    assert profile.grammar == {}
    assert profile.fluency is None


def test_get_or_create_profile_is_idempotent(db):
    first = profile_service.get_or_create_profile(db)
    db.commit()
    second = profile_service.get_or_create_profile(db)
    assert first.id == second.id


def test_update_profile_applies_theme_scores_and_increments_count(db, scenario):
    profile = profile_service.get_or_create_profile(db, scenario.target_language)
    evaluation = _evaluation(grammar=80, vocabulary=60)

    profile_service.update_profile_from_evaluation(db, profile, scenario, evaluation)

    for theme in scenario.grammar_themes:
        assert profile.grammar[theme] == pytest.approx(0.8)
    for theme in scenario.vocabulary_themes:
        assert profile.vocabulary[theme] == pytest.approx(0.6)
    assert profile.fluency == pytest.approx(0.75)
    assert profile.hesitation == pytest.approx(0.9)
    assert profile.communication_recovery == pytest.approx(0.65)
    assert profile.completed_scenarios == 1


def test_update_profile_moves_existing_score_toward_new_signal(db, scenario):
    profile = profile_service.get_or_create_profile(db, scenario.target_language)
    profile_service.update_profile_from_evaluation(db, profile, scenario, _evaluation(grammar=100))
    before = dict(profile.grammar)

    profile_service.update_profile_from_evaluation(db, profile, scenario, _evaluation(grammar=0))

    for theme in scenario.grammar_themes:
        assert profile.grammar[theme] < before[theme]
        assert profile.grammar[theme] > 0  # EMA, not a hard reset to the new signal


def test_profile_to_dict_never_includes_a_pronunciation_score(db, scenario):
    profile = profile_service.get_or_create_profile(db, scenario.target_language)
    profile_service.update_profile_from_evaluation(db, profile, scenario, _evaluation())

    data = profile_service.profile_to_dict(profile)

    assert data["pronunciation"] is None


def test_weakest_theme_picks_lowest_scored(db, scenario):
    profile = profile_service.get_or_create_profile(db, scenario.target_language)
    profile.grammar = {"present_simple": 0.9}
    profile.vocabulary = {"food": 0.2, "drinks": 0.8}

    assert profile_service.weakest_theme(profile) == "food"


def test_weakest_theme_is_none_when_profile_is_empty(db, scenario):
    profile = profile_service.get_or_create_profile(db, scenario.target_language)
    assert profile_service.weakest_theme(profile) is None
