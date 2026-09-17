import json

import pytest

from app.db.models import LearnerProfileRecord
from app.models.conversation import Transcript
from app.services.evaluation import EvaluationFailedError, LLMGatewayEvaluator
from app.services.evaluation.llm_gateway import MAX_TURNS, _build_user_message, _extract_json
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


@pytest.fixture
def profile():
    return LearnerProfileRecord(id="default", grammar={"present simple": 0.8}, vocabulary={"food": 0.6})


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


def test_user_message_mentions_injected_complications(scenario):
    message = _build_user_message(scenario, ["The item is sold out"])
    assert "The item is sold out" in message


def test_user_message_notes_when_no_complication_occurred(scenario):
    message = _build_user_message(scenario, [])
    assert "none" in message.lower()


FINAL_ANSWER = {
    "action": "final_answer",
    "evaluation": {
        "overall_score": 70,
        "grammar": 70,
        "vocabulary": 70,
        "fluency": 70,
        "hesitation": 70,
        "task_completion": 70,
        "conversation_handling": 70,
        "communication_recovery": 70,
        "weaknesses": [],
        "strengths": [],
    },
}


async def test_agent_loop_calls_tools_then_returns_final_answer(
    scenario, transcript, profile, monkeypatch: pytest.MonkeyPatch
):
    """A realistic short trace: read the transcript, ask for a
    recommendation, then answer — verifying each tool call's result
    actually lands back in the conversation before the model answers."""
    scripted_actions = [
        {"action": "call_tool", "tool": "read_transcript", "arguments": {}},
        {"action": "call_tool", "tool": "propose_next_scenario", "arguments": {"overall_score": 70}},
        FINAL_ANSWER,
    ]
    calls: list[list[dict]] = []

    async def fake_complete(self, messages):
        calls.append([dict(m) for m in messages])
        return json.dumps(scripted_actions[len(calls) - 1])

    monkeypatch.setattr(LLMGatewayEvaluator, "_complete", fake_complete)

    result = await LLMGatewayEvaluator().evaluate(
        scenario, transcript, learner_profile=profile, scenario_bank=[scenario]
    )

    assert result.overall_score == 70
    assert len(calls) == 3
    # The transcript tool's result must have been fed back before the next call.
    assert "Result of read_transcript" in calls[1][-1]["content"]
    assert "I would like a coffee" in calls[1][-1]["content"]
    assert "Result of propose_next_scenario" in calls[2][-1]["content"]


async def test_agent_loop_rejects_final_answer_before_reading_transcript(
    scenario, transcript, monkeypatch: pytest.MonkeyPatch
):
    """Observed live: the model sometimes tries to answer on turn 1 without
    calling any tools, producing a hallucinated evaluation. This must be
    rejected rather than accepted, forcing at least one real grounding call."""
    responses = [
        json.dumps(FINAL_ANSWER),
        json.dumps({"action": "call_tool", "tool": "read_transcript", "arguments": {}}),
        json.dumps(FINAL_ANSWER),
    ]

    async def fake_complete(self, messages):
        return responses.pop(0)

    monkeypatch.setattr(LLMGatewayEvaluator, "_complete", fake_complete)

    result = await LLMGatewayEvaluator().evaluate(scenario, transcript)

    assert result.overall_score == 70
    assert len(responses) == 0  # all three scripted turns were consumed


async def test_agent_loop_recovers_from_malformed_json(scenario, transcript, monkeypatch: pytest.MonkeyPatch):
    responses = [
        json.dumps({"action": "call_tool", "tool": "read_transcript", "arguments": {}}),
        "not json at all",
        json.dumps(FINAL_ANSWER),
    ]

    async def fake_complete(self, messages):
        return responses.pop(0)

    monkeypatch.setattr(LLMGatewayEvaluator, "_complete", fake_complete)

    result = await LLMGatewayEvaluator().evaluate(scenario, transcript)

    assert result.overall_score == 70


async def test_agent_loop_handles_unknown_tool_gracefully(scenario, transcript, monkeypatch: pytest.MonkeyPatch):
    responses = [
        json.dumps({"action": "call_tool", "tool": "not_a_real_tool", "arguments": {}}),
        json.dumps({"action": "call_tool", "tool": "read_transcript", "arguments": {}}),
        json.dumps(FINAL_ANSWER),
    ]

    async def fake_complete(self, messages):
        return responses.pop(0)

    monkeypatch.setattr(LLMGatewayEvaluator, "_complete", fake_complete)

    result = await LLMGatewayEvaluator().evaluate(scenario, transcript)

    assert result.overall_score == 70


async def test_agent_loop_raises_after_max_turns_without_final_answer(
    scenario, transcript, monkeypatch: pytest.MonkeyPatch
):
    async def fake_complete(self, messages):
        return json.dumps({"action": "call_tool", "tool": "read_transcript", "arguments": {}})

    monkeypatch.setattr(LLMGatewayEvaluator, "_complete", fake_complete)

    with pytest.raises(EvaluationFailedError):
        await LLMGatewayEvaluator().evaluate(scenario, transcript)


async def test_agent_loop_raises_when_final_answer_never_valid(
    scenario, transcript, monkeypatch: pytest.MonkeyPatch
):
    async def fake_complete(self, messages):
        return json.dumps({"action": "final_answer", "evaluation": {"overall_score": "not a number"}})

    monkeypatch.setattr(LLMGatewayEvaluator, "_complete", fake_complete)

    with pytest.raises(EvaluationFailedError):
        await LLMGatewayEvaluator().evaluate(scenario, transcript)


def test_max_turns_is_small_enough_to_bound_cost_and_latency():
    # Sanity guard so this doesn't silently grow into an unbounded loop.
    assert 3 <= MAX_TURNS <= 12
