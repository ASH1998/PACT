"""Intent model — stores intent contracts derived from user goals."""

from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Intent(Base):
    __tablename__ = "intents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    intent_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    user_goal: Mapped[str] = mapped_column(Text, nullable=False)
    allowed_actions_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    forbidden_actions_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    resource_scope_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    approval_required_for_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    risk_budget: Mapped[str] = mapped_column(String(50), nullable=False, default="low")
    intent_hash: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False, default="system")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
