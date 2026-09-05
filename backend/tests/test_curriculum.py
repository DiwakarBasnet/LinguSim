import pytest

from app.db.models import LearnerProfileRecord
from app.models.evaluation import EvaluationResult
from app.services import curriculum
from app.services.scenario_loader import ScenarioLoader


@pytest.fixture
def all_scenarios():
    return ScenarioLoader().list()


@pytest.fixture
def order_food(all_scenarios):
    return next(s for s in all_scenarios if s.id == "order_food")


@pytest.fixture
def hotel_problem(all_scenarios):
    return next(s for s in all_scenarios if s.id == "hotel_problem")


def _profile(**overrides) -> LearnerProfileRecord:
    profile = LearnerProfileRecord(id="default", grammar={}, vocabulary={})
    for key, value in overrides.items():
        setattr(profile, key, value)
    return profile


def _evaluation(overall_score: int) -> EvaluationResult:
    return EvaluationResult(
        overall_score=overall_score,
        grammar=overall_score,
        vocabulary=overall_score,
        fluency=overall_score,
        hesitation=overall_score,
        task_completion=overall_score,
        conversation_handling=overall_score,
    )


def test_high_score_recommends_harder_difficulty(all_scenarios, order_food):
    profile = _profile()
    recommended = curriculum.recommend_next_scenario(profile, _evaluation(90), order_food, all_scenarios)
    assert recommended.difficulty == "intermediate"


def test_low_score_recommends_easier_difficulty(all_scenarios, hotel_problem):
    profile = _profile()
    recommended = curriculum.recommend_next_scenario(profile, _evaluation(30), hotel_problem, all_scenarios)
    assert recommended.difficulty == "beginner"


def test_mid_score_holds_same_difficulty(all_scenarios, order_food):
    profile = _profile()
    recommended = curriculum.recommend_next_scenario(profile, _evaluation(65), order_food, all_scenarios)
    assert recommended.difficulty == order_food.difficulty


def test_never_recommends_the_scenario_just_played(all_scenarios, order_food):
    profile = _profile()
    recommended = curriculum.recommend_next_scenario(profile, _evaluation(65), order_food, all_scenarios)
    assert recommended.id != order_food.id


def _synthetic_scenario(id_: str, difficulty: str, grammar_themes: list[str]) -> "Scenario":
    from app.models.scenario import Scenario

    return Scenario(
        id=id_,
        title=id_,
        description="test scenario",
        target_language="English",
        difficulty=difficulty,
        ai_role="tester",
        learner_role="tester",
        objectives=["do the thing"],
        grammar_themes=grammar_themes,
    )


def test_prefers_a_scenario_matching_the_weakest_theme(order_food):
    # Two same-difficulty candidates, only one touching the weak theme — the
    # recommender should pick that one over plain list order.
    off_theme = _synthetic_scenario("off_theme", "beginner", ["present simple"])
    on_theme = _synthetic_scenario("on_theme", "beginner", ["past tense"])
    candidates = [off_theme, on_theme]

    profile = _profile(grammar={"past tense": 0.05, "present simple": 0.9})
    recommended = curriculum.recommend_next_scenario(profile, _evaluation(65), order_food, candidates)

    assert recommended.id == "on_theme"
