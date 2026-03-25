from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.core.security import normalize_email
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class User(Base, TimestampMixin, UUIDPrimaryKeyMixin):
    """Application user account used for authentication and authorization."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "email = lower(btrim(email))",
            name="ck_users_email_normalized",
        ),
    )

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    @validates("email")
    def normalize_user_email(self, _key: str, value: str) -> str:
        return normalize_email(value)
