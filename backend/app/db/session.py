from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.db.models import Base

# Columns added to existing tables after their initial release. create_all()
# only creates missing *tables*, never adds columns to ones that already
# exist, so a lightweight manual step covers the gap without pulling in a
# migration framework for a single-developer, single-environment project.
_ADDED_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "sessions": [("complications", "JSON")],
    "learner_profile": [("communication_recovery", "FLOAT")],
}


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().database_url)


def init_db() -> None:
    engine = get_engine()
    Base.metadata.create_all(engine)
    _add_missing_columns(engine)


def _add_missing_columns(engine: Engine) -> None:
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table, columns in _ADDED_COLUMNS.items():
            if table not in existing_tables:
                continue
            existing_columns = {c["name"] for c in inspector.get_columns(table)}
            for name, sql_type in columns:
                if name not in existing_columns:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {sql_type}"))


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
