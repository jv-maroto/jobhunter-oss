"""SQLAlchemy engine y session factory."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    """Base declarativa para todos los modelos ORM."""


# SQLite necesita check_same_thread=False con FastAPI workers.
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """Dependency FastAPI para inyectar sesion por request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Crea todas las tablas. Se llama en el lifespan."""
    # Import aqui para asegurar registro de modelos antes de create_all.
    from app.models import (  # noqa: F401
        api_call,
        application,
        company,
        job,
        person,
        post,
    )

    Base.metadata.create_all(bind=engine)
