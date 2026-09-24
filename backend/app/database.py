"""Lazy PostgreSQL engine and request-scoped sessions; Alembic owns DDL."""

import os
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import MetaData, create_engine
from sqlalchemy.engine import URL, Engine, make_url
from sqlalchemy.orm import DeclarativeBase, Session


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_name)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


def get_database_url() -> URL:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    value = os.getenv("DATABASE_URL")
    if not value:
        raise ValueError("Set DATABASE_URL to a PostgreSQL connection URL")
    url = make_url(value)
    if url.drivername not in {"postgresql", "postgresql+psycopg"}:
        raise ValueError("DATABASE_URL must use postgresql or postgresql+psycopg")
    return url.set(drivername="postgresql+psycopg")


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_database_url(), pool_pre_ping=True, hide_parameters=True)


def get_session() -> Iterator[Session]:
    # Callers explicitly commit successful writes. Closing rolls back unfinished work.
    with Session(get_engine()) as session:
        yield session
