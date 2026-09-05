from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class SessionRecord(Base):
    """One completed practice session: scenario played, full transcript, and
    the resulting evaluation (both stored as plain JSON — no separate
    normalized tables needed at this scale)."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    scenario_id: Mapped[str] = mapped_column(String, nullable=False)
    target_language: Mapped[str] = mapped_column(String, nullable=False)
    difficulty: Mapped[str] = mapped_column(String, nullable=False)
    transcript: Mapped[list] = mapped_column(JSON, nullable=False)
    evaluation: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class LearnerProfileRecord(Base):
    """
    Single-learner profile (no auth/multi-user support in this MVP — see
    DEFAULT_PROFILE_ID in app.services.profile_service). grammar/vocabulary
    are theme -> 0..1 mastery maps built from each scenario's own
    grammar_themes/vocabulary_themes. pronunciation is intentionally absent:
    evaluation only ever sees a text transcript, which carries no phoneme or
    acoustic signal, so no pronunciation score is ever computed or faked
    here (see app/services/evaluation).
    """

    __tablename__ = "learner_profile"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    target_language: Mapped[str] = mapped_column(String, default="English")
    level: Mapped[str] = mapped_column(String, default="A2")
    grammar: Mapped[dict] = mapped_column(JSON, default=dict)
    vocabulary: Mapped[dict] = mapped_column(JSON, default=dict)
    fluency: Mapped[float | None] = mapped_column(Float, nullable=True)
    hesitation: Mapped[float | None] = mapped_column(Float, nullable=True)
    completed_scenarios: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
