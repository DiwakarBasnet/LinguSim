import json

import pytest

from app.db.models import LearnerProfileRecord
from app.models.conversation import Transcript
from app.services.evaluation.agent_tools import build_tools
from app.services.scenario_loader import ScenarioLoader


@pytest.fixture
def scenario():
    return ScenarioLoader().get("order_food")


@pytest.fixture
def other_scenario():
    return ScenarioLoader().get("hotel_problem")


@pytest.fixture
def german_scenario():
    return ScenarioLoader().get("order_food_de")


@pytest.fixture
def transcript(scenario):
    t = Transcript(scenario_id=scenario.id)
    t.add("ai", "Hello! What can I get for you?")
    t.add("learner", "I would like a coffee, please.")
    return t


@pytest.fixture
def profile():
    return LearnerProfileRecord(
        id="default",
        grammar={"present simple": 0.9},
        vocabulary={"food": 0.2},
        communication_recovery=0.3,
    )


def test_read_transcript_formats_every_turn(scenario, transcript, profile):
    tools = build_tools(scenario, transcript, profile, [scenario])
    text = tools["read_transcript"]()
    assert "Learner: I would like a coffee, please." in text
    assert "AI: Hello! What can I get for you?" in text


def test_read_transcript_handles_empty_transcript(scenario, profile):
    empty = Transcript(scenario_id=scenario.id)
    tools = build_tools(scenario, empty, profile, [scenario])
    assert "empty transcript" in tools["read_transcript"]().lower()


def test_read_learner_profile_reports_no_data_when_absent(scenario, transcript):
    tools = build_tools(scenario, transcript, None, [scenario])
    assert "no prior profile" in tools["read_learner_profile"]().lower()


def test_read_learner_profile_serializes_real_profile_data(scenario, transcript, profile):
    tools = build_tools(scenario, transcript, profile, [scenario])
    data = json.loads(tools["read_learner_profile"]())
    assert data["vocabulary"]["food"] == 0.2
    assert data["pronunciation"] is None  # never fabricated — see LearnerProfileRecord docstring


def test_read_scenario_bank_filters_by_target_language(scenario, transcript, profile, german_scenario):
    tools = build_tools(scenario, transcript, profile, [scenario, german_scenario])
    entries = json.loads(tools["read_scenario_bank"]())
    ids = {e["id"] for e in entries}
    assert scenario.id in ids
    assert german_scenario.id not in ids  # different target_language


def test_propose_next_scenario_uses_real_curriculum_logic(scenario, other_scenario, transcript, profile):
    tools = build_tools(scenario, transcript, profile, [scenario, other_scenario])
    result = tools["propose_next_scenario"](overall_score=90)  # excelling -> harder difficulty
    assert other_scenario.title in result  # the only intermediate scenario available


def test_propose_next_scenario_tolerates_bad_input(scenario, transcript, profile):
    tools = build_tools(scenario, transcript, profile, [scenario])
    result = tools["propose_next_scenario"](overall_score="not a number")
    assert "Recommended next scenario" in result


def test_propose_next_scenario_without_profile_data(scenario, transcript):
    tools = build_tools(scenario, transcript, None, [])
    result = tools["propose_next_scenario"](overall_score=50)
    assert "No profile/scenario data" in result
