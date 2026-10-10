"""Add fields confirmed by the official Laike order query contract."""

from alembic import op
import sqlalchemy as sa


revision = "0006_laike_order_official_fields"
down_revision = "0005_laike_sync_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("laike_order") as batch_op:
        batch_op.add_column(sa.Column("account_id", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("order_status", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("pay_amount_fen", sa.BigInteger(), nullable=True))
        batch_op.add_column(sa.Column("create_order_time", sa.BigInteger(), nullable=True))
        batch_op.add_column(sa.Column("update_order_time", sa.BigInteger(), nullable=True))
        batch_op.add_column(sa.Column("pay_time", sa.BigInteger(), nullable=True))

    with op.batch_alter_table("laike_sync_cursor") as batch_op:
        batch_op.add_column(
            sa.Column("page_num", sa.Integer(), nullable=False, server_default="1")
        )
        batch_op.add_column(
            sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True)
        )

    with op.batch_alter_table("laike_sync_run") as batch_op:
        batch_op.add_column(
            sa.Column("page_count", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("fetched_count", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("succeeded_count", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("duplicate_count", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(sa.Column("error_code", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("laike_sync_run") as batch_op:
        batch_op.drop_column("error_code")
        batch_op.drop_column("duplicate_count")
        batch_op.drop_column("succeeded_count")
        batch_op.drop_column("fetched_count")
        batch_op.drop_column("page_count")

    with op.batch_alter_table("laike_sync_cursor") as batch_op:
        batch_op.drop_column("last_failure_at")
        batch_op.drop_column("last_success_at")
        batch_op.drop_column("page_num")

    with op.batch_alter_table("laike_order") as batch_op:
        batch_op.drop_column("pay_time")
        batch_op.drop_column("update_order_time")
        batch_op.drop_column("create_order_time")
        batch_op.drop_column("pay_amount_fen")
        batch_op.drop_column("order_status")
        batch_op.drop_column("account_id")
