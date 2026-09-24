"""Online/offline PostgreSQL migrations with optional injected test connection."""

from alembic import context
from sqlalchemy import create_engine, pool

from app import models  # noqa: F401 -- register all model tables
from app.database import Base, get_database_url

config = context.config
target_metadata = Base.metadata


def run(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(
        url=get_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
elif config.attributes.get("connection") is not None:
    run(config.attributes["connection"])
else:
    engine = create_engine(get_database_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        run(connection)
    engine.dispose()
