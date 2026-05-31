"""Action model — stores every attempted tool call and its envelope data."""

from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Action(Base):
    __tablename__ = "actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    step_id: Mapped[int] = mapped_column(Integer, nullable=False)
    agent_id: Mapped[str] = mapped_column(String(255), nullable=False)
    tool: Mapped[str] = mapped_column(String(255), nullable=False)
    args_digest: Mapped[str] = mapped_column(String(255), nullable=False)
    intent_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    capability_token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    provenance_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    parent_action_hash: Mapped[str] = mapped_column(String(255), nullable=True)
    action_hash: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    agent_signature: Mapped[str] = mapped_column(Text, nullable=False)
    hash_input_json: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="allowed")
    args_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    envelope_timestamp: Mapped[str] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
