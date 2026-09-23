"""Acesso ao banco, compartilhado pelo processo web e pelo ingestor.

A plataforma roda contra PostgreSQL + TimescaleDB em producao e contra SQLite no
desenvolvimento e nos testes. O modelo relacional e identico nos dois; o que difere
sao os recursos de serie temporal -- hypertable e continuous aggregates -- que sao
aplicados apenas no PostgreSQL, em :func:`apply_timescale_features`.

Essa diferenca e deliberada e limitada: as *consultas* da aplicacao sao SQL comum e
funcionam nos dois bancos. O TimescaleDB muda o desempenho da ingestao e das janelas
longas, nao a semantica.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from flask import g
from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from meliponet.models import Base

_engine: Engine | None = None
_Session: sessionmaker[Session] | None = None


def is_postgres(engine: Engine) -> bool:
    return engine.dialect.name == "postgresql"


def init_engine(database_url: str, echo: bool = False) -> Engine:
    """Cria o engine e o session factory do processo."""
    global _engine, _Session

    connect_args = {}
    if database_url.startswith("sqlite"):
        # O ingestor grava de uma thread do cliente MQTT enquanto o Flask le de outra.
        connect_args["check_same_thread"] = False

    _engine = create_engine(database_url, echo=echo, future=True, connect_args=connect_args)

    if _engine.dialect.name == "sqlite":

        @event.listens_for(_engine, "connect")
        def _sqlite_pragmas(connection, _record):  # type: ignore[no-untyped-def]
            cursor = connection.cursor()
            # WAL permite que o ingestor escreva enquanto o web le, em vez de um
            # bloquear o outro -- e o cenario normal desta aplicacao.
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

    _Session = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    return _engine


def get_engine() -> Engine:
    if _engine is None:
        raise RuntimeError("engine nao inicializado: chame init_engine() primeiro")
    return _engine


@contextmanager
def session_scope() -> Iterator[Session]:
    """Sessao transacional: commit no sucesso, rollback em qualquer excecao."""
    session = _sessionmaker()()
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

    Existe porque o template renderiza *depois* que a view retorna. Com uma sessao
    aberta e fechada dentro da view, tudo que o template fosse ler precisava ser
    carregado na marra antes -- `joinedload` defensivo, dicionario copiado a mao -- ou
    estourava `DetachedInstanceError` na hora de desenhar a pagina. Amarrando a sessao a
    requisicao inteira, o template le `colmeia.apiary.name` sem cerimonia.

    O ingestor MQTT, o CLI e os testes continuam usando ``session_scope``: nao existe
    requisicao HTTP la.
    """
    if "sessao" not in g:
        g.sessao = _sessionmaker()()
    return g.sessao


def _sessionmaker() -> sessionmaker[Session]:
    if _Session is None:
        raise RuntimeError("session factory nao inicializada: chame init_engine() primeiro")
    return _Session


def registrar_sessao_por_request(app) -> None:
    """Liga a sessao ao ciclo da requisicao: grava no sucesso, desfaz no resto.

    A regra e uma so e vale para toda rota: **requisicao que terminou bem grava; qualquer
    outra coisa desfaz**. Uma resposta 4xx ou 5xx nao commita, mesmo que a view ja tenha
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


def apply_timescale_features(engine: Engine) -> None:
    """Converte ``measurements`` em hypertable e cria os agregados continuos.

    So faz sentido no PostgreSQL com a extensao TimescaleDB; em SQLite e um no-op e a
    tabela permanece uma tabela comum, o que basta para desenvolvimento e testes.
    """
    if not is_postgres(engine):
        return

    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE"))
        connection.execute(
            text(
                "SELECT create_hypertable('measurements', 'time', "
                "if_not_exists => TRUE, migrate_data => TRUE)"
            )
        )

        # Agregados por hora e por dia. O dashboard escolhe entre a tabela bruta e
        # estes agregados conforme a janela pedida, para que "ultimos 30 dias" nao
        # varra milhoes de linhas.
        for name, bucket in (("measurements_1h", "1 hour"), ("measurements_1d", "1 day")):
            connection.execute(
                text(
                    f"""
                    CREATE MATERIALIZED VIEW IF NOT EXISTS {name}
                    WITH (timescaledb.continuous) AS
                    SELECT
                        time_bucket(INTERVAL '{bucket}', time) AS bucket,
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


def create_all(engine: Engine) -> None:
    """Cria o esquema. Em producao o Alembic assume; aqui serve para dev e testes."""
    Base.metadata.create_all(engine)
    apply_timescale_features(engine)
