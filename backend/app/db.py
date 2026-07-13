"""SQLAlchemy engine y session factory."""

from __future__ import annotations

import logging
from collections.abc import Generator

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base declarativa para todos los modelos ORM."""


# SQLite necesita check_same_thread=False con FastAPI workers.
_is_sqlite = settings.database_url.startswith("sqlite")
connect_args = {"check_same_thread": False} if _is_sqlite else {}

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
)


if _is_sqlite:
    # WAL permite lecturas concurrentes con una escritura (el scheduler puede
    # solapar con requests de la API); busy_timeout evita "database is locked"
    # esperando hasta 5s a que se libere el lock en vez de fallar al instante.
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """Dependency FastAPI para inyectar sesion por request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_columns(table: str, columns: dict[str, str]) -> None:
    """Mini-migrador idempotente para SQLite (el proyecto no usa Alembic).

    `Base.metadata.create_all` crea tablas nuevas pero NO anade columnas a una
    tabla ya existente. Este helper anade, via `ALTER TABLE ... ADD COLUMN`,
    solo las columnas que falten. Seguro de ejecutar en cada arranque.

    `columns` mapea nombre_de_columna -> definicion SQL (tipo + default), p.ej.
    {"provider": "VARCHAR(32)", "submitted_at": "DATETIME"}.
    """
    insp = inspect(engine)
    if table not in insp.get_table_names():
        return
    existing = {c["name"] for c in insp.get_columns(table)}
    with engine.begin() as conn:
        for col, ddl in columns.items():
            if col not in existing:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))
                logger.info("migrate: added column %s.%s (%s)", table, col, ddl)


def init_db() -> None:
    """Crea todas las tablas y aplica migraciones ligeras. Se llama en el lifespan."""
    # Import aqui para asegurar registro de modelos antes de create_all.
    from app.models import (  # noqa: F401
        answer_cache,
        api_call,
        application,
        apply_queue,
        company,
        email_event,
        job,
        person,
        post,
    )

    Base.metadata.create_all(bind=engine)

    # Columnas anadidas despues de la v1 del esquema (instalaciones existentes).
    ensure_columns(
        "applications",
        {
            "provider": "VARCHAR(32)",
            "apply_url": "VARCHAR(1024)",
            "screening_answers": "JSON",
            "submitted_at": "DATETIME",
        },
    )
