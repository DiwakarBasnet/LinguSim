import pytest

from app.services.scenario_loader import ScenarioLoader, ScenarioNotFoundError


@pytest.fixture
def loader() -> ScenarioLoader:
    return ScenarioLoader()


def test_loads_all_bundled_scenarios(loader: ScenarioLoader):
    scenarios = loader.list()
    assert len(scenarios) >= 4
    ids = {s.id for s in scenarios}
    assert "order_food" in ids
    assert "hotel_problem" in ids


def test_get_known_scenario(loader: ScenarioLoader):
    scenario = loader.get("order_food")
    assert scenario.title == "Ordering Food at a Cafe"
    assert scenario.difficulty == "beginner"


def test_get_unknown_scenario_raises(loader: ScenarioLoader):
    with pytest.raises(ScenarioNotFoundError):
        loader.get("does_not_exist")


def test_system_prompt_includes_role_and_objectives(loader: ScenarioLoader):
    scenario = loader.get("order_food")
    prompt = scenario.system_prompt()
    assert scenario.ai_role in prompt
    assert scenario.objectives[0] in prompt


def test_german_scenario_metadata_is_english_but_prompt_demands_german(loader: ScenarioLoader):
    scenario = loader.get("order_food_de")
    assert scenario.target_language == "German"
    # Scenario browsing metadata stays readable for a new learner...
    assert scenario.title == "Ordering Food at a Cafe"
    assert scenario.ai_role == "a friendly cafe server"
    # ...but the prompt explicitly demands the conversation itself be German.
    prompt = scenario.system_prompt()
    assert "Conduct the ENTIRE conversation in German" in prompt
