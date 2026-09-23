"""Acesso ao banco, compartilhado pelo processo web e pelo ingestor.

PostgreSQL + TimescaleDB em producao, SQLite no desenvolvimento: o modelo relacional e
o mesmo, e so os recursos de serie temporal ficam de fora do SQLite.

Duas formas de obter sessao: :func:`sessao_do_request` para as rotas web e
:func:`abrir_sessao` para quem nao tem requisicao -- ingestor, CLI e testes. O porque
esta em ``docs/guia/03-a-plataforma.md``.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from flask import Flask, g
from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

# As tabelas da Fase 4 moram num arquivo proprio, e importa-lo e o que as registra no
# `Base.metadata`. Parece um import sem uso, mas sem ele `criar_tabelas` deixaria as tres
# de fora em silencio -- `test_banco.py` existe para que apagar esta linha quebre algo.
from meliponet import modelos_futuros  # noqa: F401
from meliponet.modelos import Base

_engine: Engine | None = None
_Session: sessionmaker[Session] | None = None


def e_postgres(engine: Engine) -> bool:
    return engine.dialect.name == "postgresql"


def iniciar_banco(database_url: str, echo: bool = False) -> Engine:
    """Cria o engine e a fabrica de sessoes do processo."""
    global _engine, _Session

    connect_args = {}
    if database_url.startswith("sqlite"):
        # O ingestor grava de uma thread do cliente MQTT enquanto o Flask le de outra.
        connect_args["check_same_thread"] = False

    _engine = create_engine(database_url, echo=echo, future=True, connect_args=connect_args)

    if _engine.dialect.name == "sqlite":

        @event.listens_for(_engine, "connect")
        def _pragmas_do_sqlite(connection, _record):  # type: ignore[no-untyped-def]
            cursor = connection.cursor()
            # WAL permite que o ingestor escreva enquanto o web le, em vez de um
            # bloquear o outro -- e o cenario normal desta aplicacao.
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

    _Session = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    return _engine


def obter_engine() -> Engine:
    if _engine is None:
        raise RuntimeError("engine nao inicializado: chame iniciar_banco() primeiro")
    return _engine


def _fabrica_de_sessoes() -> sessionmaker[Session]:
    if _Session is None:
        raise RuntimeError("fabrica de sessoes nao inicializada: chame iniciar_banco() primeiro")
    return _Session


@contextmanager
def abrir_sessao() -> Iterator[Session]:
    """Sessao transacional: commit no sucesso, rollback em qualquer excecao."""
    session = _fabrica_de_sessoes()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def sessao_do_request() -> Session:
    """A sessao desta requisicao, aberta na primeira vez que alguem a pede.

    Existe porque o template renderiza *depois* que a rota retorna. Com uma sessao
    aberta e fechada dentro da rota, tudo que o template fosse ler precisava ser
    carregado na marra antes -- `joinedload` defensivo, dicionario copiado a mao -- ou
    estourava `DetachedInstanceError` na hora de desenhar a pagina. Amarrando a sessao a
    requisicao inteira, o template le `colmeia.apiary.name` sem cerimonia.
    """
    if "sessao" not in g:
        g.sessao = _fabrica_de_sessoes()()
    return g.sessao


def registrar_sessao_por_request(app: Flask) -> None:
    """Liga a sessao ao ciclo da requisicao: grava no sucesso, desfaz no resto.

    A regra e uma so e vale para toda rota: **requisicao que terminou bem grava; qualquer
    outra coisa desfaz**. Uma resposta 4xx ou 5xx nao commita, mesmo que a rota ja tenha
    mexido em algum objeto antes de desistir.
    """

    @app.after_request
    def _confirmar(response):
        sessao = g.get("sessao")
        if sessao is not None and response.status_code < 400:
            sessao.commit()
        return response

    @app.teardown_appcontext
    def _encerrar(_exc):
        sessao = g.pop("sessao", None)
        if sessao is not None:
            # Depois de um commit bem-sucedido este rollback nao faz nada; o que ele
            # cobre e o caminho que nao passou pelo `_confirmar`.
            sessao.rollback()
            sessao.close()


def ativar_timescale(engine: Engine) -> None:
    """Converte ``measurements`` em hypertable e cria os agregados continuos.

    So faz sentido no PostgreSQL com a extensao TimescaleDB; em SQLite e um no-op e a
    tabela permanece uma tabela comum, o que basta para desenvolvimento e testes.
    """
    if not e_postgres(engine):
        return

    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE"))
        connection.execute(
            text(
                "SELECT create_hypertable('measurements', 'time', "
                "if_not_exists => TRUE, migrate_data => TRUE)"
            )
        )

        # Agregados por hora e por dia. O painel escolhe entre a tabela bruta e estes
        # agregados conforme a janela pedida, para que "ultimos 30 dias" nao varra
        # milhoes de linhas.
        for nome, balde in (("measurements_1h", "1 hour"), ("measurements_1d", "1 day")):
            connection.execute(
                text(
                    f"""
                    CREATE MATERIALIZED VIEW IF NOT EXISTS {nome}
                    WITH (timescaledb.continuous) AS
                    SELECT
                        time_bucket(INTERVAL '{balde}', time) AS bucket,
                        hive_id,
                        avg(temp_in_c)   AS temp_in_c,
                        avg(temp_out_c)  AS temp_out_c,
                        avg(rh_in_pct)   AS rh_in_pct,
                        avg(rh_out_pct)  AS rh_out_pct,
                        avg(weight_kg)   AS weight_kg,
                        min(vbat_v)      AS vbat_v,
                        count(*)         AS sample_count
                    FROM measurements
                    GROUP BY bucket, hive_id
                    WITH NO DATA
                    """
                )
            )


def criar_tabelas(engine: Engine) -> None:
    """Cria o esquema. Em producao o Alembic assume; aqui serve para dev e testes."""
    Base.metadata.create_all(engine)
    ativar_timescale(engine)
