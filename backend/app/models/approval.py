"""Approval model — tracks human approval requests for sensitive actions."""

from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    approval_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    action_hash: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    requested_by_agent_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by: Mapped[str] = mapped_column(String(255), nullable=True)
    decision_reason: Mapped[str] = mapped_column(Text, nullable=True)
    approval_token_hash: Mapped[str] = mapped_column(String(255), nullable=True)
    approved_envelope_digest: Mapped[str] = mapped_column(String(255), nullable=True)
    envelope_json: Mapped[str] = mapped_column(Text, nullable=True)
