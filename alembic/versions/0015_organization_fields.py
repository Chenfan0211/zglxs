"""Expand organization module fields to match legacy frontend."""

from alembic import op
import sqlalchemy as sa


revision = "0015_organization_fields"
down_revision = "0014_account_product"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # department 补字段
    with op.batch_alter_table("department") as batch_op:
        batch_op.add_column(sa.Column("dept_type", sa.String(length=32), nullable=False, server_default="live"))
        batch_op.add_column(sa.Column("ordid", sa.Integer(), nullable=False, server_default="255"))

    # staff 补字段
    with op.batch_alter_table("staff") as batch_op:
        batch_op.add_column(sa.Column("service_cate_id", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("password", sa.String(length=128), nullable=True))

    # account 补字段
    with op.batch_alter_table("account") as batch_op:
        batch_op.add_column(sa.Column("account_name", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("account_id", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("check_msg", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("memo", sa.Text(), nullable=True))

    # custom_service_group 补字段
    with op.batch_alter_table("custom_service_group") as batch_op:
        batch_op.add_column(sa.Column("allocation_type", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("department_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("web_hook", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("memo", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("ordid", sa.Integer(), nullable=False, server_default="0"))

    # custom_service_group_member 补字段
    with op.batch_alter_table("custom_service_group_member") as batch_op:
        batch_op.add_column(sa.Column("custom_uid", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("rate", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("day_limit_num", sa.Integer(), nullable=True))

    # account_product 补字段
    with op.batch_alter_table("account_product") as batch_op:
        batch_op.add_column(sa.Column("out_product_id", sa.String(length=255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("department") as batch_op:
        batch_op.drop_column("dept_type")
        batch_op.drop_column("ordid")
    with op.batch_alter_table("staff") as batch_op:
        batch_op.drop_column("service_cate_id")
        batch_op.drop_column("password")
    with op.batch_alter_table("account") as batch_op:
        batch_op.drop_column("account_name")
        batch_op.drop_column("account_id")
        batch_op.drop_column("check_msg")
        batch_op.drop_column("memo")
    with op.batch_alter_table("custom_service_group") as batch_op:
        batch_op.drop_column("allocation_type")
        batch_op.drop_column("department_id")
        batch_op.drop_column("web_hook")
        batch_op.drop_column("memo")
        batch_op.drop_column("ordid")
    with op.batch_alter_table("custom_service_group_member") as batch_op:
        batch_op.drop_column("custom_uid")
        batch_op.drop_column("rate")
        batch_op.drop_column("day_limit_num")
    with op.batch_alter_table("account_product") as batch_op:
        batch_op.drop_column("out_product_id")
