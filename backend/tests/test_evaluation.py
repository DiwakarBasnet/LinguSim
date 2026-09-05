import pytest

from app.models.conversation import Transcript
from app.services.evaluation.llm_gateway import _extract_json
from app.services.evaluation.mock import MockEvaluator
from app.services.scenario_loader import ScenarioLoader


@pytest.fixture
def scenario():
    return ScenarioLoader().get("order_food")


@pytest.fixture
def transcript(scenario):
    t = Transcript(scenario_id=scenario.id)
    t.add("ai", "Hello! What can I get for you?")
    t.add("learner", "I would like a coffee and a croissant please, thank you very much.")
    t.add("ai", "Coming right up.")
    t.add("learner", "Great, thanks.")
    return t


async def test_mock_evaluator_produces_valid_result(scenario, transcript):
    result = await MockEvaluator().evaluate(scenario, transcript)
    for field in ("overall_score", "grammar", "vocabulary", "fluency", "hesitation", "task_completion", "conversation_handling"):
        value = getattr(result, field)
        assert 0 <= value <= 100


async def test_mock_evaluator_handles_empty_transcript(scenario):
    empty = Transcript(scenario_id=scenario.id)
    result = await MockEvaluator().evaluate(scenario, empty)
    assert result.task_completion == 0
    assert result.conversation_handling == 30


def test_extract_json_plain():
    assert _extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_with_code_fence():
    text = '```json\n{"a": 1, "b": [1, 2]}\n```'
    assert _extract_json(text) == {"a": 1, "b": [1, 2]}


def test_extract_json_with_surrounding_prose():
    text = 'Sure, here is the result:\n{"a": 1}\nHope that helps!'
    assert _extract_json(text) == {"a": 1}


def test_extract_json_raises_when_no_object_present():
    with pytest.raises(ValueError):
        _extract_json("no json here")
