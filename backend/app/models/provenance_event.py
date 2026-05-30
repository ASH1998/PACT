"""Provenance Event model — stores provenance tracking events."""

from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ProvenanceEvent(Base):
    __tablename__ = "provenance_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_uri: Mapped[str] = mapped_column(Text, nullable=True)
    source_label: Mapped[str] = mapped_column(String(255), nullable=True)
    sensitivity: Mapped[str] = mapped_column(String(50), nullable=False, default="low")
    produced_by_action_hash: Mapped[str] = mapped_column(String(255), nullable=True)
    parent_event_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    content_digest: Mapped[str] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
