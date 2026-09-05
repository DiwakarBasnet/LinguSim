import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import SessionRecord
from app.db.session import get_db
from app.models.evaluation import EvaluationResult
from app.services import curriculum, profile_service
from app.services.scenario_loader import ScenarioLoader, ScenarioNotFoundError, get_scenario_loader

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profile", tags=["profile"])


def _recommended_scenario_id(db: Session, profile, loader: ScenarioLoader) -> str | None:
    """Recomputed from the most recent session (if any) — the recommendation
    itself is never persisted, only derived on read from current state."""
    last_session = db.execute(
        select(SessionRecord).order_by(SessionRecord.created_at.desc()).limit(1)
    ).scalar_one_or_none()
    if last_session is None:
        return None
    try:
        scenario = loader.get(last_session.scenario_id)
    except ScenarioNotFoundError:
        return None
    evaluation = EvaluationResult.model_validate(last_session.evaluation)
    try:
        return curriculum.recommend_next_scenario(profile, evaluation, scenario, loader.list()).id
    except Exception:
        logger.warning("recommendation_failed", exc_info=True)
        return None


@router.get("")
async def get_profile(
    db: Session = Depends(get_db), loader: ScenarioLoader = Depends(get_scenario_loader)
) -> dict:
    profile = profile_service.get_or_create_profile(db)
    db.commit()
    data = profile_service.profile_to_dict(profile)
    data["recommended_scenario_id"] = _recommended_scenario_id(db, profile, loader)
    return data
