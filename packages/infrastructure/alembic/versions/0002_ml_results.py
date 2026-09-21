"""Dataset provenance, run results and lifecycle events.

Revision ID: 0002_ml_results
Revises: 0001_foundation
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_ml_results"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("result_artifact", sa.String(255)))
    op.add_column("runs", sa.Column("result_sha256", sa.String(64)))
    op.add_column("runs", sa.Column("summary", sa.JSON()))
    op.add_column("runs", sa.Column("dataset_hash", sa.String(64)))
    op.add_column("runs", sa.Column("fingerprint", sa.String(64)))
    op.add_column("runs", sa.Column("error_detail_artifact", sa.String(255)))
    op.create_table(
        "dataset_versions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.String(64), unique=True, nullable=False),
        sa.Column("archive_sha256", sa.String(64), nullable=False),
        sa.Column("arff_sha256", sa.String(64), nullable=False),
        sa.Column("manifest_path", sa.String(255), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rows", sa.Integer(), nullable=False),
        sa.Column("feature_count", sa.Integer(), nullable=False),
        sa.Column("classes", sa.JSON(), nullable=False),
    )
    op.create_table(
        "run_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.String(255)),
    )
    op.create_index("ix_run_events_run_id", "run_events", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_run_events_run_id", table_name="run_events")
    op.drop_table("run_events")
    op.drop_table("dataset_versions")
    for name in (
        "error_detail_artifact",
        "fingerprint",
        "dataset_hash",
        "summary",
        "result_sha256",
        "result_artifact",
    ):
        op.drop_column("runs", name)
