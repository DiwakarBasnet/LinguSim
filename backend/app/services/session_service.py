import logging
from uuid import uuid4

from sqlalchemy.orm import Session

from app.db.models import SessionRecord
from app.models.conversation import Transcript
from app.models.scenario import Scenario
from app.services import curriculum, profile_service
from app.services.evaluation import LLMGatewayEvaluator
from app.services.scenario_loader import ScenarioLoader

logger = logging.getLogger(__name__)


class SessionService:
    """Persists a finished session, evaluates it, and updates the learner
    profile + next-scenario recommendation in one place."""

    def __init__(self, db: Session, evaluator: LLMGatewayEvaluator, scenario_loader: ScenarioLoader):
        self.db = db
        self.evaluator = evaluator
        self.scenario_loader = scenario_loader

    async def finish_session(
        self, scenario: Scenario, transcript: Transcript, complications: list[str] | None = None
    ) -> dict:
        complications = complications or []
        evaluation = await self.evaluator.evaluate(scenario, transcript, complications)

        record = SessionRecord(
            id=uuid4().hex,
            scenario_id=scenario.id,
            target_language=scenario.target_language,
            difficulty=scenario.difficulty,
            transcript=[turn.model_dump() for turn in transcript.turns],
            evaluation=evaluation.model_dump(),
            complications=complications,
        )
        self.db.add(record)

        profile = profile_service.get_or_create_profile(self.db, scenario.target_language)
        profile = profile_service.update_profile_from_evaluation(self.db, profile, scenario, evaluation)

        recommended = curriculum.recommend_next_scenario(
            profile, evaluation, scenario, self.scenario_loader.list()
        )

        self.db.commit()
        logger.info(
            "session_finished",
            extra={"context": {"scenario_id": scenario.id, "overall_score": evaluation.overall_score}},
        )

        return {
            "session_id": record.id,
            "evaluation": evaluation.model_dump(),
            "profile": profile_service.profile_to_dict(profile),
            "recommended_scenario_id": recommended.id,
        }
