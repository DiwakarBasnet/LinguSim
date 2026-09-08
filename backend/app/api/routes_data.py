import logging

from fastapi import APIRouter, Depends
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db.models import LearnerProfileRecord, SessionRecord
from app.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data", tags=["data"])


@router.delete("")
async def clear_all_data(db: Session = Depends(get_db)) -> dict:
    """Wipes every session and the learner profile — a full reset, since
    this is a single-learner MVP with no accounts to scope a delete to."""
    db.execute(delete(SessionRecord))
    db.execute(delete(LearnerProfileRecord))
    db.commit()
    logger.info("all_data_cleared")
    return {"status": "cleared"}
