import json
import logging
import re

import httpx

from app.config import get_settings
from app.models.conversation import Transcript
from app.models.evaluation import EvaluationResult
from app.models.scenario import Scenario
from app.services.evaluation.base import Evaluator
from app.services.evaluation.mock import MockEvaluator

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a language-learning coach evaluating a practice conversation.
You are given the scenario the learner practiced and a full transcript. Assess ONLY what is
actually present in the transcript text — do not assume anything about pronunciation or audio
quality, since you were not given any audio; if asked to judge pronunciation you must refuse,
but you are not asked to here.

Respond with ONLY a single JSON object (no markdown fences, no commentary) with exactly these
fields:
{
  "overall_score": <0-100 int>,
  "grammar": <0-100 int, grammatical correctness of the learner's turns>,
  "vocabulary": <0-100 int, range/appropriateness of vocabulary used>,
  "fluency": <0-100 int, how naturally the learner expressed themselves>,
  "hesitation": <0-100 int, HIGHER = fewer fillers/hesitations/restarts>,
  "task_completion": <0-100 int, how well the learner achieved the scenario's objectives>,
  "conversation_handling": <0-100 int, appropriateness/relevance of the learner's responses>,
  "weaknesses": [<short strings, prefer the scenario's own grammar/vocabulary theme names>],
  "strengths": [<short strings>]
}"""

_JSON_OBJECT_PATTERN = re.compile(r"\{.*\}", re.DOTALL)


def _format_transcript(transcript: Transcript) -> str:
    lines = []
    for turn in transcript.turns:
        speaker = "Learner" if turn.speaker == "learner" else "AI"
        lines.append(f"{speaker}: {turn.text}")
    return "\n".join(lines)


def _build_user_message(scenario: Scenario, transcript: Transcript) -> str:
    return (
        f"Scenario: {scenario.title}\n"
        f"Learner's role: {scenario.learner_role}\n"
        f"Objectives: {'; '.join(scenario.objectives) or 'none listed'}\n"
        f"Success criteria: {'; '.join(scenario.success_criteria) or 'none listed'}\n"
        f"Grammar themes: {', '.join(scenario.grammar_themes) or 'none'}\n"
        f"Vocabulary themes: {', '.join(scenario.vocabulary_themes) or 'none'}\n\n"
        f"Transcript:\n{_format_transcript(transcript)}"
    )


def _extract_json(text: str) -> dict:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        stripped = stripped.split("\n", 1)[1] if "\n" in stripped else stripped
    match = _JSON_OBJECT_PATTERN.search(stripped)
    if not match:
        raise ValueError("No JSON object found in model output")
    return json.loads(match.group(0))


class LLMGatewayEvaluator(Evaluator):
    """
    Real evaluator using AssemblyAI's LLM Gateway (OpenAI-compatible chat
    completions, same API key as the voice agent). The account this was
    built against only has access to a fast model without native
    response_format/JSON-schema support, so structured output is obtained
    via prompt instructions + best-effort JSON extraction and Pydantic
    validation, with one retry and a fallback to MockEvaluator if the model
    output still doesn't parse. If a stronger model with response_format
    support becomes available on the account, prefer that instead.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._fallback = MockEvaluator()

    async def evaluate(self, scenario: Scenario, transcript: Transcript) -> EvaluationResult:
        user_message = _build_user_message(scenario, transcript)

        for attempt in range(2):
            try:
                raw = await self._complete(user_message, retry=attempt > 0)
                data = _extract_json(raw)
                return EvaluationResult.model_validate(data)
            except Exception:
                logger.warning("llm_gateway_evaluation_parse_failed", exc_info=True, extra={"context": {"attempt": attempt}})

        logger.error("llm_gateway_evaluation_failed_falling_back_to_mock")
        return await self._fallback.evaluate(scenario, transcript)

    async def _complete(self, user_message: str, retry: bool) -> str:
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]
        if retry:
            messages.append(
                {
                    "role": "user",
                    "content": "Your previous response was not a single valid JSON object. "
                    "Respond again with ONLY the JSON object, nothing else.",
                }
            )

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                self._settings.llm_gateway_url,
                headers={"authorization": self._settings.assemblyai_api_key},
                json={
                    "model": self._settings.llm_gateway_model,
                    "messages": messages,
                    "max_tokens": 600,
                },
            )
            response.raise_for_status()
            body = response.json()
            return body["choices"][0]["message"]["content"]
