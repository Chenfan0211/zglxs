"""Add follow status table."""

from alembic import op
import sqlalchemy as sa


revision = "0013_follow_status"
down_revision = "0012_custom_group_live_room"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "follow_status",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("follow_status")
