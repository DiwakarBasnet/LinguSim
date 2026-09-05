from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.db.models import Base


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().database_url)


def init_db() -> None:
    Base.metadata.create_all(get_engine())


def create_session() -> Session:
    """For call sites that aren't FastAPI HTTP routes (e.g. the WebSocket
    handler), where a Depends(get_db) generator doesn't apply."""
    return sessionmaker(bind=get_engine(), expire_on_commit=False)()


def get_db() -> Generator[Session, None, None]:
    db = create_session()
    try:
        yield db
    finally:
        db.close()
