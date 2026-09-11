"""Add webhook claim fencing token."""

from alembic import op
import sqlalchemy as sa


revision = "0003_laike_claim_token"
down_revision = "0002_laike_sync"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "laike_webhook_event",
        sa.Column("claim_token", sa.String(length=36), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("laike_webhook_event", "claim_token")
