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


def test_laike_migration_runs_on_sqlite_and_drops_sync_tables(tmp_path):
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

    command.downgrade(config, "0001_baseline")
    tables_after_downgrade = set(inspect(engine).get_table_names())
    assert not (
        tables_after_downgrade
        & {
            "laike_webhook_event",
            "laike_order",
            "laike_sync_cursor",
            "laike_sync_run",
        }
    )
