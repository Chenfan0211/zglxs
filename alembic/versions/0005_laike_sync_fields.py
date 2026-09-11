"""Complete Laike synchronization persistence fields."""

from alembic import op
import sqlalchemy as sa


revision = "0005_laike_sync_fields"
down_revision = "0004_laike_retry_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "laike_webhook_event",
        sa.Column(
            "source",
            sa.String(length=255),
            nullable=False,
            server_default="laike",
        ),
    )
    op.add_column(
        "laike_webhook_event",
        sa.Column("error_reason", sa.Text(), nullable=True),
    )
    with op.batch_alter_table("laike_order") as batch_op:
        batch_op.add_column(
            sa.Column("subject_id", sa.String(length=255), nullable=True)
        )
        batch_op.add_column(
            sa.Column("product_id", sa.String(length=255), nullable=True)
        )
        batch_op.add_column(
            sa.Column("original_created_at", sa.JSON(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "normalized_created_at",
                sa.String(length=255),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column("original_updated_at", sa.JSON(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "normalized_updated_at",
                sa.String(length=255),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "first_discovered_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            )
        )
        batch_op.add_column(
            sa.Column(
                "last_updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("laike_order") as batch_op:
        batch_op.drop_column("last_updated_at")
        batch_op.drop_column("first_discovered_at")
        batch_op.drop_column("normalized_updated_at")
        batch_op.drop_column("original_updated_at")
        batch_op.drop_column("normalized_created_at")
        batch_op.drop_column("original_created_at")
        batch_op.drop_column("product_id")
        batch_op.drop_column("subject_id")
    op.drop_column("laike_webhook_event", "error_reason")
    op.drop_column("laike_webhook_event", "source")
