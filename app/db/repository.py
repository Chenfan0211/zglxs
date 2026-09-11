from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import Table, select
from sqlalchemy.orm import Session


class SqlAlchemyRepository:
    def __init__(self, session: Session, table: Table):
        self._session = session
        self._table = table

    def get_by_id(self, value: Any) -> dict[str, Any] | None:
        row = self._session.execute(
            select(self._table).where(self._table.c.id == value)
        ).mappings().first()
        return None if row is None else dict(row)

    def list(self, filters: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
        statement = select(self._table)
        for name, value in (filters or {}).items():
            if name not in self._table.c:
                raise ValueError(f"unknown filter column: {name}")
            column = self._table.c[name]
            statement = statement.where(column == value)
        return [dict(row) for row in self._session.execute(statement).mappings().all()]

    def insert(self, values: Mapping[str, Any]) -> dict[str, Any]:
        result = self._session.execute(self._table.insert().values(**dict(values)))
        if "id" in values:
            inserted_id = values["id"]
        elif result.inserted_primary_key:
            inserted_id = result.inserted_primary_key[0]
        else:
            return dict(values)
        row = self.get_by_id(inserted_id)
        return row or dict(values)
