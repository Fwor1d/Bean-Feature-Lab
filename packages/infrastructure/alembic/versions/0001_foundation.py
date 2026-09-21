"""Foundation metadata tables.

Revision ID: 0001_foundation
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "0001_foundation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "experiments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("experiment_id", sa.Integer(), sa.ForeignKey("experiments.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("error", sa.Text()),
    )
    op.create_index("ix_runs_experiment_id", "runs", ["experiment_id"])
    op.create_table(
        "worker_heartbeat",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("seen_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("worker_heartbeat")
    op.drop_index("ix_runs_experiment_id", table_name="runs")
    op.drop_table("runs")
    op.drop_table("experiments")
