"""Add custom group live room association table."""

from alembic import op
import sqlalchemy as sa


revision = "0012_custom_group_live_room"
down_revision = "0011_system_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "custom_group_live_room",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("live_room_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("custom_group_live_room")
