from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import SessionRecord
from app.db.session import get_db
from app.services.scenario_loader import ScenarioLoader, get_scenario_loader

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("")
async def list_sessions(
    db: Session = Depends(get_db), loader: ScenarioLoader = Depends(get_scenario_loader)
) -> list[dict]:
    records = db.execute(select(SessionRecord).order_by(SessionRecord.created_at.asc())).scalars().all()
    results = []
    for record in records:
        try:
            title = loader.get(record.scenario_id).title
        except KeyError:
            title = record.scenario_id
        results.append(
            {
                "id": record.id,
                "scenario_id": record.scenario_id,
                "scenario_title": title,
                "difficulty": record.difficulty,
                "evaluation": record.evaluation,
                "created_at": record.created_at.isoformat(),
            }
        )
    return results
