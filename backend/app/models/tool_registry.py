"""Tool Registry model — stores registered tool metadata in the database."""

from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ToolRegistry(Base):
    __tablename__ = "tool_registry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tool_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False, default="1.0.0")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    input_schema_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    output_schema_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    side_effect: Mapped[str] = mapped_column(String(50), nullable=False, default="none")
    resource_type: Mapped[str] = mapped_column(String(255), nullable=False, default="default")
    resource_extractor_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    sensitivity: Mapped[str] = mapped_column(String(50), nullable=False, default="low")
    default_requires_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
