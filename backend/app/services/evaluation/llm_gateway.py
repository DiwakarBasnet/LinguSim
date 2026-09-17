import asyncio
import json
import logging
import re

import httpx

from app.config import get_settings
from app.db.models import LearnerProfileRecord
from app.models.conversation import Transcript
from app.models.evaluation import EvaluationResult
from app.models.scenario import Scenario
from app.services.evaluation.agent_tools import build_tools

logger = logging.getLogger(__name__)


class EvaluationFailedError(RuntimeError):
    pass


# The account this was built against only has access to a fast model
# without native tool-calling/response_format support (see llm_gateway_model
# in config.py), so this is a manually-orchestrated ReAct-style loop rather
# than the LLM Gateway's native function-calling: the model emits a small
# JSON "action" describing which tool to call or its final answer, this
# code executes the actual tool and feeds the result back as another
# message, repeating until a valid final_answer arrives or MAX_TURNS is hit.
# This is provider-agnostic — it would keep working even on a model with no
# tool-calling support of any kind — and is genuinely multi-step: each tool
# call is a real request/response round-trip with the model, not simulated.
MAX_TURNS = 8

_AGENT_SYSTEM_PROMPT = """You are a simulation coach for a language-learning app, evaluating a
learner's just-finished voice simulation. Use tools to gather what you need before judging —
don't guess at the transcript, the learner's history, or what to recommend next.

Respond with ONLY a single JSON object each turn (no markdown fences, no commentary), in exactly
one of these two shapes:

To call a tool:
{"action": "call_tool", "tool": "<tool name>", "arguments": {...}}

To give your final answer:
{"action": "final_answer", "evaluation": {
  "overall_score": <0-100 int>,
  "grammar": <0-100 int, grammatical correctness of the learner's turns>,
  "vocabulary": <0-100 int, range/appropriateness of vocabulary used>,
  "fluency": <0-100 int, how naturally the learner expressed themselves>,
  "hesitation": <0-100 int, HIGHER = fewer fillers/hesitations/restarts>,
  "task_completion": <0-100 int, how well the learner achieved the scenario's objectives>,
  "conversation_handling": <0-100 int, appropriateness/relevance of the learner's responses>,
  "communication_recovery": <0-100 int, see below>,
  "weaknesses": [<short strings, prefer the scenario's own grammar/vocabulary theme names>],
  "strengths": [<short strings>]
}}

Available tools:
- read_transcript: no arguments. Returns the full conversation transcript.
- read_learner_profile: no arguments. Returns the learner's tracked grammar/vocabulary mastery
  and fluency/hesitation/communication_recovery scores from BEFORE this session.
- read_scenario_bank: no arguments. Returns every available scenario (id, title, difficulty,
  grammar/vocabulary themes, how many complications it can throw) in this learner's language.
- propose_next_scenario: {"overall_score": <0-100 int, your assessment of THIS session>}.
  Returns a real next-scenario recommendation, chosen the same way the app's curriculum engine
  always does. Call this once you have an overall_score in mind, so your "weaknesses" point at
  an actual next step instead of a vague suggestion.

communication_recovery scores how well the learner handled being misunderstood, surprised, or
hit with an injected complication mid-conversation — clarifying, rephrasing, adapting, still
working toward the task. If the transcript notes no complication occurred, score ordinary
conversational repair instead. Assess ONLY what is actually present in the transcript text — do
not assume anything about pronunciation or audio quality, since you were not given any audio; if
asked to judge pronunciation you must refuse, but you are not asked to here.

Always call read_transcript first. Prefer calling each other tool at most once. You have a
limited number of turns, so move toward a final_answer once you have enough to judge fairly."""

_JSON_OBJECT_PATTERN = re.compile(r"\{.*\}", re.DOTALL)


def _build_user_message(scenario: Scenario, complications: list[str]) -> str:
    complications_line = (
        "; ".join(complications) if complications else "none — the conversation ran without a scripted complication"
    )
    return (
        f"Evaluate this session.\n"
        f"Scenario: {scenario.title}\n"
        f"Learner's role: {scenario.learner_role}\n"
        f"Objectives: {'; '.join(scenario.objectives) or 'none listed'}\n"
        f"Success criteria: {'; '.join(scenario.success_criteria) or 'none listed'}\n"
        f"Complications injected mid-conversation: {complications_line}\n\n"
        f"Start by calling read_transcript."
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


class LLMGatewayEvaluator:
    """
    Evaluator using AssemblyAI's LLM Gateway (OpenAI-compatible chat
    completions, same API key as the voice agent) as a small tool-using
    agent — see MAX_TURNS above for why this is a manual loop rather than
    native function-calling, and agent_tools.py for what the four tools do.
    """

    def __init__(self) -> None:
        self._settings = get_settings()

    async def evaluate(
        self,
        scenario: Scenario,
        transcript: Transcript,
        complications: list[str] | None = None,
        learner_profile: LearnerProfileRecord | None = None,
        scenario_bank: list[Scenario] | None = None,
    ) -> EvaluationResult:
        tools = build_tools(scenario, transcript, learner_profile, scenario_bank or [])

        messages = [
            {"role": "system", "content": _AGENT_SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_message(scenario, complications or [])},
        ]

        # The model isn't reliably following "always call read_transcript
        # first" as a mere instruction — observed live returning a
        # final_answer on turn 1 with fabricated content (references to
        # things never in the transcript). Enforcing read_transcript as a
        # hard precondition for accepting final_answer is what actually
        # guarantees the evaluation is grounded, rather than hoping the
        # prompt is followed.
        called_tools: set[str] = set()

        last_error: Exception | None = None
        for turn in range(MAX_TURNS):
            try:
                raw = await self._complete(messages)
            except Exception as exc:
                last_error = exc
                logger.warning("llm_gateway_agent_request_failed", exc_info=True, extra={"context": {"turn": turn}})
                break

            try:
                action = _extract_json(raw)
            except Exception as exc:
                last_error = exc
                logger.warning("llm_gateway_agent_bad_json", extra={"context": {"turn": turn, "raw": raw[:200]}})
                messages.append({"role": "assistant", "content": raw})
                messages.append(
                    {"role": "user", "content": "Respond with ONLY one JSON object, exactly as instructed."}
                )
                continue

            messages.append({"role": "assistant", "content": raw})

            if action.get("action") == "final_answer":
                if "read_transcript" not in called_tools:
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "You haven't called read_transcript yet — you cannot judge this session "
                                "without reading it. Call read_transcript now."
                            ),
                        }
                    )
                    continue
                try:
                    return EvaluationResult.model_validate(action.get("evaluation", {}))
                except Exception as exc:
                    last_error = exc
                    logger.warning("llm_gateway_agent_invalid_final_answer", extra={"context": {"turn": turn}})
                    messages.append(
                        {"role": "user", "content": "That evaluation JSON was invalid. Give a corrected final_answer."}
                    )
                    continue

            if action.get("action") == "call_tool":
                tool_name = action.get("tool")
                tool_fn = tools.get(tool_name)
                if tool_fn is None:
                    messages.append(
                        {
                            "role": "user",
                            "content": f"Unknown tool '{tool_name}'. Available tools: {', '.join(tools)}.",
                        }
                    )
                    continue
                arguments = action.get("arguments") or {}
                result = tool_fn(**arguments) if isinstance(arguments, dict) else tool_fn()
                called_tools.add(tool_name)
                logger.info(
                    "evaluator_agent_tool_call",
                    extra={"context": {"turn": turn, "tool": tool_name, "scenario_id": scenario.id}},
                )
                messages.append({"role": "user", "content": f"Result of {tool_name}: {result}"})
                continue

            messages.append({"role": "user", "content": "Invalid action — use 'call_tool' or 'final_answer'."})

        raise EvaluationFailedError("Evaluator agent did not produce a final answer in time") from last_error

    async def _complete(self, messages: list[dict]) -> str:
        """
        The agent loop makes several of these per evaluation (one per tool
        call plus one for the final answer), several times more than the
        old single-prompt evaluator — so a rate limit is meaningfully more
        likely to be hit mid-loop than it used to be. A short backoff retry
        on 429 specifically (distinct from the malformed-JSON retry in
        evaluate()) keeps one rate-limited turn from failing the whole
        session's evaluation.
        """
        async with httpx.AsyncClient(timeout=30) as client:
            for attempt in range(3):
                response = await client.post(
                    self._settings.llm_gateway_url,
                    headers={"authorization": self._settings.assemblyai_api_key},
                    json={
                        "model": self._settings.llm_gateway_model,
                        "messages": messages,
                        "max_tokens": 600,
                    },
                )
                if response.status_code == 429 and attempt < 2:
                    delay = float(response.headers.get("retry-after", 2 * (attempt + 1)))
                    logger.warning(
                        "llm_gateway_rate_limited", extra={"context": {"attempt": attempt, "delay": delay}}
                    )
                    await asyncio.sleep(delay)
                    continue
                response.raise_for_status()
                body = response.json()
                return body["choices"][0]["message"]["content"]
            raise EvaluationFailedError("LLM Gateway is rate-limited")
