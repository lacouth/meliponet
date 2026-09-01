"""Testes das séries que alimentam os gráficos.

O foco é uma propriedade central para o projeto: **uma lacuna precisa aparecer como
lacuna**. Os indicadores de completude do Edital 17 perdem o sentido se a interface
desenhar uma linha contínua por cima das mensagens que nunca chegaram.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from meliponet.db import create_all, init_engine, session_scope
from meliponet.models import Apiary, Hive, Measurement
from meliponet.services import series as series_service


@pytest.fixture
def hive_id(tmp_path) -> int:
    engine = init_engine(f"sqlite:///{tmp_path / 'series.sqlite3'}")
    create_all(engine)
    with session_scope() as session:
        apiary = Apiary(name="Meliponário de teste")
        session.add(apiary)
        session.flush()
        hive = Hive(apiary_id=apiary.id, name="Colmeia 01")
        session.add(hive)
        session.flush()
        return hive.id


def fill(hive_id: int, *, count: int, skip: frozenset[int] = frozenset()) -> None:
    """Grava ``count`` leituras a cada 5 min, pulando os índices em ``skip``."""
    now = datetime.now(UTC)
    with session_scope() as session:
        for index in range(count):
            if index in skip:
                continue
            session.add(
                Measurement(
                    time=now - timedelta(minutes=5 * (count - index)),
                    node_id="A4C13800",
                    hive_id=hive_id,
                    # A seq avança mesmo nas leituras puladas: é assim que o nó real se
                    # comporta, e é o que torna a perda contável.
                    seq=index + 1,
                    temp_in_c=30.0,
                    temp_out_c=34.0,
                    weight_kg=12.0,
                )
            )


def test_lacuna_vira_null_e_nao_ponto_ausente(hive_id: int) -> None:
    fill(hive_id, count=60, skip=frozenset({20, 21, 22}))

    with session_scope() as session:
        points = series_service.series(session, hive_id, "24h")

    valores = [p.values["temp_in_c"] for p in points]
    # Buracos internos à série: descarta a cauda vazia anterior à primeira leitura.
    primeiro = next(i for i, v in enumerate(valores) if v is not None)
    ultimo = len(valores) - 1 - next(i for i, v in enumerate(reversed(valores)) if v is not None)
    internos = valores[primeiro : ultimo + 1]

    assert internos.count(None) >= 3, "as leituras puladas precisam virar buracos na série"
    assert all(v is None or v == pytest.approx(30.0) for v in internos)


def test_serie_cobre_a_janela_inteira(hive_id: int) -> None:
    """A grade de pontos não depende de quantas leituras chegaram.

    288 baldes de 5 min em 24 h, com folga de um para o alinhamento das bordas.
    """
    fill(hive_id, count=10)

    with session_scope() as session:
        points = series_service.series(session, hive_id, "24h")

    assert len(points) in (288, 289)


def test_baldes_sao_estaveis_entre_consultas(hive_id: int) -> None:
    """Dois refreshes seguidos não podem deslocar os pontos do gráfico.

    Por isso os baldes são ancorados na epoca, e não na primeira leitura da consulta.
    """
    fill(hive_id, count=30)

    with session_scope() as session:
        primeiro = [p.time for p in series_service.series(session, hive_id, "24h")]
        segundo = [p.time for p in series_service.series(session, hive_id, "24h")]

    assert primeiro == segundo


def test_completude_conta_saltos_de_seq(hive_id: int) -> None:
    """Completude vem dos saltos em ``seq``, medida direta, não de estimativa por tempo."""
    fill(hive_id, count=40, skip=frozenset({5, 6, 17}))

    with session_scope() as session:
        resultado = series_service.completeness(session, hive_id, "24h")

    assert resultado["received"] == 37
    assert resultado["expected"] == 40
    assert resultado["gaps"] == 3


def test_colmeia_sem_leitura(hive_id: int) -> None:
    with session_scope() as session:
        assert series_service.latest(session, hive_id) is None
        assert series_service.completeness(session, hive_id, "24h")["received"] == 0
