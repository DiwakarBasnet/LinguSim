from app.services.evaluation.base import Evaluator
from app.services.evaluation.mock import MockEvaluator

__all__ = ["Evaluator", "MockEvaluator", "create_evaluator"]


def create_evaluator(provider: str) -> Evaluator:
    if provider == "mock":
        return MockEvaluator()
    if provider == "llm_gateway":
        from app.services.evaluation.llm_gateway import LLMGatewayEvaluator

        return LLMGatewayEvaluator()
    raise ValueError(f"Unknown evaluation provider: {provider}")
