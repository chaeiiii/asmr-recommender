"""Shared real-PostgreSQL fixtures isolated from existing database contents."""

import os
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from dotenv import load_dotenv


@pytest.fixture(scope="module")
def migrated():
    backend = Path(__file__).resolve().parents[1]
    load_dotenv(backend / ".env")
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to run real PostgreSQL tests")
    parsed = sa.engine.make_url(url)
    if parsed.drivername not in {"postgresql", "postgresql+psycopg"}:
        pytest.fail("TEST_DATABASE_URL must point to PostgreSQL")
    engine = sa.create_engine(parsed.set(drivername="postgresql+psycopg"))
    schema = "asmr_test_" + uuid4().hex
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(sa.schema.CreateSchema(schema))
            connection.execute(sa.text(f'SET LOCAL search_path TO "{schema}"'))
            engine.dialect.default_schema_name = schema
            config = Config(str(backend / "alembic.ini"))
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            yield connection, config
        finally:
            transaction.rollback()
    engine.dispose()


@pytest.fixture
def db(migrated):
    connection, _ = migrated
    with connection.begin_nested() as transaction:
        yield connection
        transaction.rollback()
