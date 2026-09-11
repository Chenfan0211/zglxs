from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine

from app.db.schema_catalog import SchemaCatalog


def test_schema_catalog_reflects_existing_tables_without_guessing_columns():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata = MetaData()
    Table(
        "dydd_demo",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("status", String(20), nullable=False),
    )
    metadata.create_all(engine)

    catalog = SchemaCatalog(engine)

    assert catalog.snapshot() == {
        "dydd_demo": [
            {"name": "id", "type": "INTEGER", "nullable": False},
            {"name": "status", "type": "VARCHAR(20)", "nullable": False},
        ]
    }
