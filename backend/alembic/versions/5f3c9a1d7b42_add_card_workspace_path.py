"""add card workspace_path

Revision ID: 5f3c9a1d7b42
Revises: 8c6d06d7d97d
Create Date: 2026-11-27 16:20:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "5f3c9a1d7b42"
down_revision: str | None = "8c6d06d7d97d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("service_cards", schema=None) as batch_op:
        batch_op.add_column(sa.Column("workspace_path", sa.String(length=1024), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("service_cards", schema=None) as batch_op:
        batch_op.drop_column("workspace_path")
