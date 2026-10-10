from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


class Database:
    def __init__(self, database_url: str | None):
        self._database_url = database_url
        self._engine: Engine | None = None
        self._session_factory: sessionmaker[Session] | None = None

    @property
    def database_url(self) -> str | None:
        return self._database_url

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

    def session(self) -> Session:
        if self._session_factory is None:
            self._session_factory = sessionmaker(
                bind=self._get_engine(),
                expire_on_commit=False,
            )
        return self._session_factory()

    def dispose(self) -> None:
        if self._engine is not None:
            self._engine.dispose()


class UnitOfWork:
    def __init__(self, session_factory):
        self._session_factory = session_factory
        self.session: Session | None = None

    def __enter__(self) -> "UnitOfWork":
        self.session = self._session_factory()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        assert self.session is not None
        try:
            if exc_type is None:
                self.session.commit()
            else:
                self.session.rollback()
        finally:
            self.session.close()
        return False
