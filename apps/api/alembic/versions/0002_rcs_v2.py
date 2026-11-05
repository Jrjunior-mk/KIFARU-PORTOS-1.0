"""RCS v2 — port-anchored clearance: tokens, release orders, permits, node/stream/dimension columns, station kinds

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-05
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from kifaru.models import Base

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

NEW_TABLES = ["core.load_compliance_tokens", "core.release_orders", "core.special_load_permits"]

NEW_COLUMNS = {
    ("core", "weighing_stations"): [sa.Column("kind", sa.String(16), nullable=False, server_default="road_station")],
    ("core", "lanes"): [sa.Column("legal_grade", sa.Boolean(), nullable=False, server_default=sa.false())],
    ("core", "vehicles"): [
        sa.Column("trust_tier", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("demerit_points", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("enrolled_at", sa.DateTime(timezone=True), nullable=True),
    ],
    ("core", "weighing_events"): [
        sa.Column("node_kind", sa.String(20), nullable=False, server_default="road_mainline"),
        sa.Column("stream", sa.String(12), nullable=False, server_default="untokened"),
        sa.Column("length_m", sa.Float(), nullable=True),
        sa.Column("width_m", sa.Float(), nullable=True),
        sa.Column("height_m", sa.Float(), nullable=True),
        sa.Column("lifted_axle", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("token_id", sa.CHAR(26), nullable=True),
    ],
    ("core", "clearance_decisions"): [
        sa.Column("route", sa.String(20), nullable=False, server_default="continue"),
        sa.Column("token_checked_id", sa.CHAR(26), nullable=True),
        sa.Column("token_issued_id", sa.CHAR(26), nullable=True),
        sa.Column("fee_preview_usd", sa.Float(), nullable=True),
    ],
}


def _has_column(bind, schema: str, table: str, column: str) -> bool:
    insp = sa.inspect(bind)
    cols = insp.get_columns(table, schema=schema if bind.dialect.name == "postgresql" else None)
    return any(c["name"] == column for c in cols)


def upgrade() -> None:
    bind = op.get_bind()
    pg = bind.dialect.name == "postgresql"
    for (schema, table), cols in NEW_COLUMNS.items():
        for col in cols:
            if not _has_column(bind, schema, table, col.name):
                op.add_column(table, col, schema=schema if pg else None)
    # new tables (create_all only creates what is missing)
    Base.metadata.create_all(bind=bind, tables=[Base.metadata.tables[t] for t in NEW_TABLES])
    if pg:
        op.execute(sa.text("ALTER TABLE core.lanes ALTER COLUMN type TYPE VARCHAR(24)"))
        op.create_index("ix_weighing_events_token_id", "weighing_events", ["token_id"], schema="core", if_not_exists=True)


def downgrade() -> None:
    bind = op.get_bind()
    pg = bind.dialect.name == "postgresql"
    for t in reversed(NEW_TABLES):
        Base.metadata.tables[t].drop(bind=bind, checkfirst=True)
    if pg:
        for (schema, table), cols in NEW_COLUMNS.items():
            for col in cols:
                op.drop_column(table, col.name, schema=schema)
    # SQLite cannot drop columns portably before 3.35; the added columns are harmless there.
