from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import uuid
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ExtractionResult(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "extraction_results"
    __table_args__ = (
        Index("idx_extraction_results_document_type", "document_type"),
        Index("idx_extraction_results_confidence", "confidence_score"),
    )

    workflow_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflow_runs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    document_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    extracted_fields: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    raw_llm_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    extraction_method: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tokens_used: Mapped[int | None] = mapped_column(nullable=True)
    reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_fields: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)