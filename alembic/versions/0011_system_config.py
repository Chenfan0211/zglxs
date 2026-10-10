"""Add system config tables."""

from alembic import op
import sqlalchemy as sa


revision = "0011_system_config"
down_revision = "0010_order"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_config",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("config_key", sa.String(length=128), nullable=False, unique=True),
        sa.Column("config_value", sa.Text(), nullable=True),
        sa.Column("remark", sa.String(length=255), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "table_column_setting",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("table_key", sa.String(length=128), nullable=False),
        sa.Column("user_key", sa.String(length=128), nullable=False, server_default="default"),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("table_column_setting")
    op.drop_table("system_config")
