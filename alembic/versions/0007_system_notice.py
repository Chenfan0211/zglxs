"""Add system_notice table for dashboard notices."""

from alembic import op
import sqlalchemy as sa


revision = "0007_system_notice"
down_revision = "0006_laike_order_official_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_notice",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "notice_type",
            sa.String(length=32),
            nullable=False,
            server_default="system",
        ),
        sa.Column(
            "is_published",
            sa.Boolean(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("system_notice")
