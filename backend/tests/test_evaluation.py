import pytest

from app.models.conversation import Transcript
from app.services.evaluation import EvaluationFailedError, LLMGatewayEvaluator
from app.services.evaluation.llm_gateway import _build_user_message, _extract_json
from app.services.scenario_loader import ScenarioLoader


@pytest.fixture
def scenario():
    return ScenarioLoader().get("order_food")


@pytest.fixture
def transcript(scenario):
    t = Transcript(scenario_id=scenario.id)
    t.add("ai", "Hello! What can I get for you?")
    t.add("learner", "I would like a coffee and a croissant please, thank you very much.")
    return t


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


def test_user_message_mentions_injected_complications(scenario, transcript):
    message = _build_user_message(scenario, transcript, ["The item is sold out"])
    assert "The item is sold out" in message


def test_user_message_notes_when_no_complication_occurred(scenario, transcript):
    message = _build_user_message(scenario, transcript, [])
    assert "none" in message.lower()


VALID_RESULT_JSON = (
    '{"overall_score": 70, "grammar": 70, "vocabulary": 70, "fluency": 70, '
    '"hesitation": 70, "task_completion": 70, "conversation_handling": 70, '
    '"communication_recovery": 70, "weaknesses": [], "strengths": []}'
)


async def test_llm_gateway_evaluator_retries_once_on_malformed_output(
    scenario, transcript, monkeypatch: pytest.MonkeyPatch
):
    calls = []

    async def fake_complete(self, user_message, retry):
        calls.append(retry)
        return "not json at all" if not retry else VALID_RESULT_JSON

    monkeypatch.setattr(LLMGatewayEvaluator, "_complete", fake_complete)

    result = await LLMGatewayEvaluator().evaluate(scenario, transcript)

    assert calls == [False, True]
    assert result.overall_score == 70


async def test_llm_gateway_evaluator_raises_after_two_failed_attempts(
    scenario, transcript, monkeypatch: pytest.MonkeyPatch
):
    async def fake_complete(self, user_message, retry):
        return "still not json"

    monkeypatch.setattr(LLMGatewayEvaluator, "_complete", fake_complete)

    with pytest.raises(EvaluationFailedError):
        await LLMGatewayEvaluator().evaluate(scenario, transcript)
