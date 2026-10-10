"""Add order business extension tables."""

from alembic import op
import sqlalchemy as sa


revision = "0010_order"
down_revision = "0009_live"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "order_follow",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("provider_order_id", sa.String(length=255), nullable=False, index=True),
        sa.Column("follow_status", sa.String(length=32), nullable=False, server_default="new"),
        sa.Column("owner_staff_id", sa.Integer(), nullable=True),
        sa.Column("follow_day", sa.Integer(), nullable=True),
        sa.Column("memo", sa.Text(), nullable=True),
        sa.Column("tel", sa.String(length=32), nullable=True),
        sa.Column("lock_flag", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "order_follow_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("provider_order_id", sa.String(length=255), nullable=False, index=True),
        sa.Column("staff_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "order_claim",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("provider_order_id", sa.String(length=255), nullable=False, index=True),
        sa.Column("staff_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="claimed"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    for table in ("order_claim", "order_follow_log", "order_follow"):
        op.drop_table(table)
