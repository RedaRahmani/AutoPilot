"""pre auth cleanup

Revision ID: 7f9c2d4e1a6b
Revises: 0bd06dd1f533
Create Date: 2026-03-25 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7f9c2d4e1a6b"
down_revision: Union[str, Sequence[str], None] = "0bd06dd1f533"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("UPDATE users SET email = lower(btrim(email))")
    op.create_check_constraint(
        "ck_users_email_normalized",
        "users",
        "email = lower(btrim(email))",
    )

    op.drop_column("review_queue_items", "deleted_at")
    op.drop_column("extraction_results", "deleted_at")
    op.drop_column("workflow_runs", "deleted_at")
    op.drop_column("documents", "deleted_at")
    op.drop_column("workflows", "deleted_at")
    op.drop_column("users", "deleted_at")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "users",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "workflows",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "workflow_runs",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "extraction_results",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "review_queue_items",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.drop_constraint("ck_users_email_normalized", "users", type_="check")
