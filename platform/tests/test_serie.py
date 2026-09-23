"""Testes das séries que alimentam os gráficos.

O foco é uma propriedade central para o projeto: **uma lacuna precisa aparecer como
lacuna**. Os indicadores de completude do Edital 17 perdem o sentido se a interface
desenhar uma linha contínua por cima das mensagens que nunca chegaram.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from meliponet.banco import abrir_sessao
from meliponet.modelos import Medicao
from meliponet.servicos import serie as servico_de_serie


@pytest.fixture
def colmeia_id(cenario) -> int:
    return cenario.colmeia_id


def preencher(colmeia_id: int, *, quantas: int, pular: frozenset[int] = frozenset()) -> None:
    """Grava ``quantas`` leituras a cada 5 min, pulando os indices em ``pular``."""
    agora = datetime.now(UTC)
    with abrir_sessao() as session:
        for indice in range(quantas):
            if indice in pular:
                continue
            session.add(
                Medicao(
                    time=agora - timedelta(minutes=5 * (quantas - indice)),
                    node_id="A4C13800",
                    hive_id=colmeia_id,
                    # A seq avança mesmo nas leituras puladas: é assim que o nó real se
                    # comporta, e é o que torna a perda contável.
                    seq=indice + 1,
                    temp_in_c=30.0,
                    temp_out_c=34.0,
                    weight_kg=12.0,
                )
            )


def test_lacuna_vira_null_e_nao_ponto_ausente(colmeia_id: int) -> None:
    preencher(colmeia_id, quantas=60, pular=frozenset({20, 21, 22}))

    with abrir_sessao() as session:
        pontos = servico_de_serie.serie(session, colmeia_id, "24h")

    valores = [p.values["temp_in_c"] for p in pontos]
    # Buracos internos à série: descarta a cauda vazia anterior à primeira leitura.
    primeiro = next(i for i, v in enumerate(valores) if v is not None)
    ultimo = len(valores) - 1 - next(i for i, v in enumerate(reversed(valores)) if v is not None)
    internos = valores[primeiro : ultimo + 1]

    assert internos.count(None) >= 3, "as leituras puladas precisam virar buracos na série"
    assert all(v is None or v == pytest.approx(30.0) for v in internos)


def test_serie_cobre_a_janela_inteira(colmeia_id: int) -> None:
    """A grade de pontos não depende de quantas leituras chegaram.

    288 baldes de 5 min em 24 h, com folga de um para o alinhamento das bordas.
    """
    preencher(colmeia_id, quantas=10)

    with abrir_sessao() as session:
        pontos = servico_de_serie.serie(session, colmeia_id, "24h")

    assert len(pontos) in (288, 289)


def test_baldes_sao_estaveis_entre_consultas(colmeia_id: int) -> None:
    """Dois refreshes seguidos não podem deslocar os pontos do gráfico.

    Por isso os baldes são ancorados na epoca, e não na primeira leitura da consulta.
    """
    preencher(colmeia_id, quantas=30)

    with abrir_sessao() as session:
        primeiro = [p.time for p in servico_de_serie.serie(session, colmeia_id, "24h")]
        segundo = [p.time for p in servico_de_serie.serie(session, colmeia_id, "24h")]

    assert primeiro == segundo


def test_completude_conta_saltos_de_seq(colmeia_id: int) -> None:
    """Completude vem dos saltos em ``seq``, medida direta, não de estimativa por tempo."""
    preencher(colmeia_id, quantas=40, pular=frozenset({5, 6, 17}))

    with abrir_sessao() as session:
        resultado = servico_de_serie.completude(session, colmeia_id, "24h")

    assert resultado["received"] == 37
    assert resultado["expected"] == 40
    assert resultado["gaps"] == 3


def test_colmeia_sem_leitura(colmeia_id: int) -> None:
    with abrir_sessao() as session:
        assert servico_de_serie.ultima_leitura(session, colmeia_id) is None
        assert servico_de_serie.completude(session, colmeia_id, "24h")["received"] == 0
