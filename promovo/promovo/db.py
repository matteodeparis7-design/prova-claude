"""Connessione al database e sessioni."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


def make_engine(url: str) -> Engine:
    kwargs: dict = {}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if url in ("sqlite://", "sqlite:///:memory:"):
            kwargs["poolclass"] = StaticPool
    engine = create_engine(url, **kwargs)
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _record):  # pragma: no cover - dettaglio del driver
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()
    return engine


class Database:
    def __init__(self, url: str):
        self.engine = make_engine(url)
        self._factory = sessionmaker(bind=self.engine, expire_on_commit=False, class_=Session)

    def create_all(self) -> None:
        from . import models
        assert models.Base is Base  # importare i modelli li registra nei metadati
        Base.metadata.create_all(self.engine)
        self.upgrade_columns()

    def upgrade_columns(self) -> list[str]:
        """Aggiunge ai database esistenti le colonne nate con le versioni nuove, senza perdere dati.

        Le tabelle nuove le crea create_all; qui si completano quelle già esistenti.
        """
        added: list[str] = []
        insp = inspect(self.engine)
        with self.engine.begin() as conn:
            for table in Base.metadata.sorted_tables:
                if not insp.has_table(table.name):
                    continue
                present = {c["name"] for c in insp.get_columns(table.name)}
                for col in table.columns:
                    if col.name in present:
                        continue
                    ddl_type = col.type.compile(dialect=self.engine.dialect)
                    default = _sql_default(col)
                    clause = f" DEFAULT {default}" if default is not None else ""
                    conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {ddl_type}{clause}'))
                    added.append(f"{table.name}.{col.name}")
        return added


    @contextmanager
    def session(self) -> Iterator[Session]:
        s = self._factory()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    def new_session(self) -> Session:
        return self._factory()


def _sql_default(col) -> str | None:
    """Valore predefinito SQL per una colonna aggiunta a una tabella esistente."""
    d = col.default
    if d is None or not getattr(d, "is_scalar", False):
        if d is not None and callable(getattr(d, "arg", None)):
            arg = d.arg
            name = getattr(arg, "__name__", "")
            if name in ("list", "<lambda>") or arg is list:
                return "'[]'"
            if arg is dict:
                return "'{}'"
        return None if col.nullable else "''"
    v = d.arg
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (int, float)):
        return str(v)
    if hasattr(v, "value"):          # enum
        v = v.value
    return "'" + str(v).replace("'", "''") + "'"
