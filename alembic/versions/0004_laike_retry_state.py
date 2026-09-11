"""Persist webhook retry counters and scanner delivery leases."""

from alembic import op
import sqlalchemy as sa


revision = "0004_laike_retry_state"
down_revision = "0003_laike_claim_token"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "laike_webhook_event",
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "laike_webhook_event",
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "laike_webhook_event",
        sa.Column("retry_scheduled_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("laike_webhook_event", "retry_scheduled_at")
    op.drop_column("laike_webhook_event", "next_retry_at")
    op.drop_column("laike_webhook_event", "retry_count")
