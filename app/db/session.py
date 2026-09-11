from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


class Database:
    def __init__(self, database_url: str | None):
        self._database_url = database_url
        self._engine: Engine | None = None

    def _get_engine(self) -> Engine:
        if not self._database_url:
            raise RuntimeError("database is not configured")
        if self._engine is None:
            self._engine = create_engine(
                self._database_url,
                pool_pre_ping=True,
            )
        return self._engine

    def check(self) -> bool:
        engine = self._get_engine()
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True

    def dispose(self) -> None:
        if self._engine is not None:
            self._engine.dispose()
