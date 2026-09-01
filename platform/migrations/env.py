"""Ambiente do Alembic.

A URL do banco vem de ``DATABASE_URL``, a mesma variavel que a aplicacao e o ingestor
usam -- e nao de ``alembic.ini``. Duas fontes de verdade para o endereco do banco
acabariam, mais cedo ou mais tarde, com uma migracao aplicada no banco errado.
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meliponet.config import Config
from meliponet.models import Base

config = context.config
config.set_main_option("sqlalchemy.url", Config.from_env().database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def render_item(type_, obj, autogen_context):
    """Renderiza ``UtcDateTime`` como o tipo SQL que ele de fato e.

    Sem isto, o autogenerate escreve ``meliponet.models.UtcDateTime()`` no arquivo de
    migracao, que nem sequer importa esse modulo. Renderizar o tipo subjacente resolve
    o import e, mais importante, mantem as migracoes independentes do codigo da
    aplicacao: uma migracao antiga precisa continuar rodando anos depois, mesmo que a
    classe tenha sido renomeada ou removida.
    """
    if type_ == "type" and obj.__class__.__name__ == "UtcDateTime":
        # `sa` ja vem importado pelo template script.py.mako.
        return "sa.DateTime(timezone=True)"
    return False


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        render_item=render_item,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_item=render_item,
            # O SQLite nao suporta ALTER de coluna; o batch mode recria a tabela por
            # baixo. Sem isso, uma migracao futura rodaria no PostgreSQL e falharia no
            # ambiente de desenvolvimento.
            render_as_batch=connection.dialect.name == "sqlite",
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
