"""SmartPort port-process layer: port_visits table

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-05
"""
from __future__ import annotations

from alembic import op

from kifaru.models import Base

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

NEW_TABLES = ["core.port_visits"]


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, tables=[Base.metadata.tables[t] for t in NEW_TABLES])


def downgrade() -> None:
    bind = op.get_bind()
    for t in reversed(NEW_TABLES):
        Base.metadata.tables[t].drop(bind=bind, checkfirst=True)
