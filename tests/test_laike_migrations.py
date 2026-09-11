from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_laike_migration_declares_all_sync_tables_and_reversible_operations():
    revision = (
        Path(__file__).parents[1] / "alembic/versions/0002_laike_sync.py"
    ).read_text(encoding="utf-8")

    assert 'revision = "0002_laike_sync"' in revision
    assert 'down_revision = "0001_baseline"' in revision
    for table_name in (
        "laike_webhook_event",
        "laike_order",
        "laike_sync_cursor",
        "laike_sync_run",
    ):
        assert f'"{table_name}"' in revision
    assert "def upgrade" in revision
    assert "def downgrade" in revision
    assert "op.drop_table" in revision

    claim_revision = (
        Path(__file__).parents[1] / "alembic/versions/0003_laike_claim_token.py"
    ).read_text(encoding="utf-8")
    assert 'revision = "0003_laike_claim_token"' in claim_revision
    assert 'down_revision = "0002_laike_sync"' in claim_revision
    assert 'sa.Column("claim_token"' in claim_revision
    assert "op.add_column" in claim_revision
    assert "op.drop_column" in claim_revision

    retry_revision = (
        Path(__file__).parents[1] / "alembic/versions/0004_laike_retry_state.py"
    )
    assert retry_revision.exists()
    retry_text = retry_revision.read_text(encoding="utf-8")
    assert 'revision = "0004_laike_retry_state"' in retry_text
    assert 'down_revision = "0003_laike_claim_token"' in retry_text
    assert 'sa.Column("retry_count"' in retry_text
    assert 'sa.Column("next_retry_at"' in retry_text
    assert 'sa.Column("retry_scheduled_at"' in retry_text


def test_laike_migration_downgrades_claim_column_then_sync_tables_on_sqlite(tmp_path):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'migration.db'}"
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    tables = set(inspect(engine).get_table_names())

    assert tables >= {
        "alembic_version",
        "laike_webhook_event",
        "laike_order",
        "laike_sync_cursor",
        "laike_sync_run",
    }
    assert {
        column["name"] for column in inspect(engine).get_columns("laike_order")
    } >= {"provider_order_id", "payload_json", "status", "created_at"}
    assert "claim_token" in {
        column["name"]
        for column in inspect(engine).get_columns("laike_webhook_event")
    }
    assert {
        column["name"]
        for column in inspect(engine).get_columns("laike_webhook_event")
    } >= {"retry_count", "next_retry_at", "retry_scheduled_at"}

    command.downgrade(config, "0002_laike_sync")
    tables_after_downgrade = set(inspect(engine).get_table_names())
    assert "claim_token" not in {
        column["name"]
        for column in inspect(engine).get_columns("laike_webhook_event")
    }
    assert tables_after_downgrade >= {
        "alembic_version",
        "laike_webhook_event",
        "laike_order",
        "laike_sync_cursor",
        "laike_sync_run",
    }

    command.downgrade(config, "0001_baseline")
    tables_after_full_downgrade = set(inspect(engine).get_table_names())
    assert not (
        tables_after_full_downgrade
        & {
            "laike_webhook_event",
            "laike_order",
            "laike_sync_cursor",
            "laike_sync_run",
        }
    )
