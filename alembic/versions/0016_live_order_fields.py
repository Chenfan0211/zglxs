"""Expand live and order module fields to match legacy frontend."""

from alembic import op
import sqlalchemy as sa


revision = "0016_live_order_fields"
down_revision = "0015_organization_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # live_room 补字段
    with op.batch_alter_table("live_room") as batch_op:
        batch_op.add_column(sa.Column("live_uid", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("live_uuid", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("memo", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("ordid", sa.Integer(), nullable=False, server_default="0"))

    # live_room_member 补字段
    with op.batch_alter_table("live_room_member") as batch_op:
        batch_op.add_column(sa.Column("anchor_uid", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("is_control", sa.Boolean(), nullable=False, server_default="0"))

    # live_room_console 补字段
    with op.batch_alter_table("live_room_console") as batch_op:
        batch_op.add_column(sa.Column("console_uid", sa.String(length=128), nullable=True))

    # order_follow 补字段
    with op.batch_alter_table("order_follow") as batch_op:
        batch_op.add_column(sa.Column("custom_department_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("custom_service_group_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("custom_cate_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("custom_staff_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("custom_allocation_time", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("custom_allocation_type", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("maintenance_department_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("maintenance_staff_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("live_room_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("anchor_staff_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("console_staff_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("sale_user_role", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("sale_channel", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("sale_user_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("add_price_fen", sa.BigInteger(), nullable=True))
        batch_op.add_column(sa.Column("refund_money_fen", sa.BigInteger(), nullable=True))
        batch_op.add_column(sa.Column("refund_type", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("cost_amount_fen", sa.BigInteger(), nullable=True))
        batch_op.add_column(sa.Column("profit_amount_fen", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("live_room") as batch_op:
        batch_op.drop_column("live_uid")
        batch_op.drop_column("live_uuid")
        batch_op.drop_column("memo")
        batch_op.drop_column("ordid")
    with op.batch_alter_table("live_room_member") as batch_op:
        batch_op.drop_column("anchor_uid")
        batch_op.drop_column("is_control")
    with op.batch_alter_table("live_room_console") as batch_op:
        batch_op.drop_column("console_uid")
    cols = [
        "custom_department_id", "custom_service_group_id", "custom_cate_id",
        "custom_staff_id", "custom_allocation_time", "custom_allocation_type",
        "maintenance_department_id", "maintenance_staff_id", "live_room_id",
        "anchor_staff_id", "console_staff_id", "sale_user_role", "sale_channel",
        "sale_user_id", "add_price_fen", "refund_money_fen", "refund_type",
        "cost_amount_fen", "profit_amount_fen",
    ]
    with op.batch_alter_table("order_follow") as batch_op:
        for c in cols:
            batch_op.drop_column(c)
