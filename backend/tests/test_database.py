from io import StringIO
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from app.database import get_database_url


def test_database_url_requires_postgresql(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///test.db")
    with pytest.raises(ValueError, match="PostgreSQL|postgresql"):
        get_database_url()


def test_database_url_uses_psycopg_and_preserves_escaped_password(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:p%25ss@localhost/test")
    url = get_database_url()
    assert url.drivername == "postgresql+psycopg"
    assert url.password == "p%ss"


def test_offline_migration(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:unused@localhost/test")
    output = StringIO()
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.output_buffer = output
    command.upgrade(config, "head", sql=True)
    sql = output.getvalue()
    assert sql.count("CREATE TABLE ") == 14  # 13 product tables + Alembic version
    assert "JSONB" in sql
    assert "TIMESTAMP WITH TIME ZONE" in sql
    assert "created_at DESC" in sql
