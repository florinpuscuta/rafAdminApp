import asyncio
import importlib
import pkgutil
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import settings
from app.core.db import Base


def _import_all_module_models() -> None:
    """Import `models` din fiecare pachet din `app.modules.*` ca Alembic să
    vadă toate modelele fără ca Alembic sau main.py să le enumere manual.
    Regula: un modul nou = un folder nou în `app/modules/<nume>/` cu `models.py`.
    """
    import app.modules as modules_pkg

    for module_info in pkgutil.iter_modules(modules_pkg.__path__):
        if not module_info.ispkg:
            continue
        try:
            importlib.import_module(f"app.modules.{module_info.name}.models")
        except ModuleNotFoundError:
            continue


_import_all_module_models()

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
