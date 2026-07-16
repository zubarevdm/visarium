"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-07-07

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from pgvector.sqlalchemy import Vector

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

EMBEDDING_DIM = 384


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("telegram_id", sa.BigInteger, nullable=False, unique=True),
        sa.Column("language", sa.String(8), nullable=False, server_default="ru"),
        sa.Column("subscription_status", sa.String(16), nullable=False, server_default="free"),
        sa.Column("subscription_expires_at", sa.DateTime(timezone=True)),
        sa.Column("teaser_sent_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"])

    op.create_table(
        "user_profiles",
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("citizenship", sa.String(8)),
        sa.Column("entry_date", sa.Date),
        sa.Column("migration_registered", sa.Boolean),
        sa.Column("has_patent", sa.Boolean),
        sa.Column("patent_date", sa.Date),
        sa.Column("has_rvp", sa.Boolean),
        sa.Column("has_vnj", sa.Boolean),
        sa.Column("goal", sa.String(16)),
        sa.Column("current_stage", sa.String(32)),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "dialog_state",
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("collected_facts", JSONB, nullable=False, server_default="{}"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "deadlines",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("due_date", sa.Date, nullable=False),
        sa.Column("notified_7d", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("notified_3d", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("notified_1d", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
    )
    op.create_index("ix_deadlines_user_id", "deadlines", ["user_id"])
    op.create_index("ix_deadlines_due_status", "deadlines", ["due_date", "status"])

    op.create_table(
        "kb_chunks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("stage", sa.String(32), nullable=False),
        sa.Column("applies_to", ARRAY(sa.Text), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.Column("source_file", sa.String(255), nullable=False),
        sa.Column("kb_version", sa.String(64), nullable=False),
    )
    op.create_index("ix_kb_chunks_stage", "kb_chunks", ["stage"])
    op.execute(
        "CREATE INDEX ix_kb_chunks_embedding ON kb_chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )

    op.create_table(
        "payments",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("telegram_payment_charge_id", sa.String(255), nullable=False, unique=True),
        sa.Column("stars_amount", sa.Integer, nullable=False),
        sa.Column("period", sa.String(16), nullable=False, server_default="1m"),
        sa.Column("status", sa.String(16), nullable=False, server_default="completed"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_payments_user_id", "payments", ["user_id"])


def downgrade() -> None:
    op.drop_table("payments")
    op.drop_table("kb_chunks")
    op.drop_table("deadlines")
    op.drop_table("dialog_state")
    op.drop_table("user_profiles")
    op.drop_table("users")
