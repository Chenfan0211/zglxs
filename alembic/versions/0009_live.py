"""Add live module tables."""

from alembic import op
import sqlalchemy as sa


revision = "0009_live"
down_revision = "0008_organization"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "live_room",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("department_id", sa.Integer(), nullable=True),
        sa.Column("room_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "live_room_member",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("live_room_id", sa.Integer(), nullable=False),
        sa.Column("staff_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="anchor"),
        sa.Column("status", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "live_room_console",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("live_room_id", sa.Integer(), nullable=False),
        sa.Column("staff_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "work_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("live_room_id", sa.Integer(), nullable=True),
        sa.Column("staff_id", sa.Integer(), nullable=True),
        sa.Column("work_type", sa.String(length=32), nullable=False, server_default="start"),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    for table in ("work_log", "live_room_console", "live_room_member", "live_room"):
        op.drop_table(table)
