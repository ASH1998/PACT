"""Model Event model — records LLM interaction events."""

from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ModelEvent(Base):
    __tablename__ = "model_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(255), nullable=False)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    request_json: Mapped[str] = mapped_column(Text, nullable=True)
    response_json: Mapped[str] = mapped_column(Text, nullable=True)
    tool_calls_json: Mapped[str] = mapped_column(Text, nullable=True)
    token_usage_json: Mapped[str] = mapped_column(Text, nullable=True)
    raw_request_json: Mapped[str] = mapped_column(Text, nullable=True)
    raw_response_json: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
