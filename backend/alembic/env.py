from logging.config import fileConfig
from sqlalchemy import create_engine
from alembic import context

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Database URL from alembic.ini
db_url = config.get_main_option("sqlalchemy.url")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    context.configure(
        url=db_url,
        target_metadata=None,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    engine = create_engine(db_url)

    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=None,
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
