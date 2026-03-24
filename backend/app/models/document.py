from __future__ import annotations

import uuid

from sqlalchemy import BigInteger, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin, TimestampMixin


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Represents an uploaded document stored by the system."""
    __tablename__ = "documents"
    __table_args__ = (
    Index("idx_documents_uploaded_by", "uploaded_by"),
    Index("idx_documents_created_at", "created_at"),
    )

    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    storage_backend: Mapped[str] = mapped_column(String(50), nullable=False, default="local")
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )