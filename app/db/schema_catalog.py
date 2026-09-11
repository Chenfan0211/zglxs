from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy import inspect
from sqlalchemy.engine import Engine


class SchemaCatalog:
    def __init__(self, engine: Engine):
        self._engine = engine

    def table_names(self) -> list[str]:
        return sorted(inspect(self._engine).get_table_names())

    def snapshot(self, tables: Iterable[str] | None = None) -> dict[str, list[dict[str, Any]]]:
        inspector = inspect(self._engine)
        names = sorted(tables or inspector.get_table_names())
        return {
            name: [
                {
                    "name": column["name"],
                    "type": str(column["type"]),
                    "nullable": bool(column["nullable"]),
                }
                for column in inspector.get_columns(name)
            ]
            for name in names
        }
