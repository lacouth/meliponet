"""Testes da ingestao: da mensagem MQTT ate a linha no banco."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from meliponet.banco import abrir_sessao
from meliponet.ingestao.gravacao import gravar, registrar_recusa
from meliponet.ingestao.telemetria import decodificar
from meliponet.modelos import Medicao, No, Recusa, Vinculo
from mensagem import ESQUEMA, serializar
from sqlalchemy import select


def message(seq: int, *, ts: datetime | None = None, node_id: str = "A4C13800", **extra) -> str:
    when = ts or datetime.now(UTC) - timedelta(minutes=seq)
    payload = {
        "schema": ESQUEMA,
        "node_id": node_id,
        "seq": seq,
        "ts": when.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "temp_in_c": 30.1,
        "temp_out_c": 34.2,
        "weight_kg": 12.4,
        **extra,
    }
    return serializar(payload)


def test_grava_leitura(scenario) -> None:
    with abrir_sessao() as session:
        resultado = gravar(session, decodificar(message(1)))

    assert resultado.stored
    assert resultado.hive_id == scenario.hive_id

    with abrir_sessao() as session:
        row = session.scalar(select(Medicao))
        assert row.temp_in_c == pytest.approx(30.1)
        assert row.diferencial_termico_c == pytest.approx(-4.1)


def test_reenvio_do_spool_e_idempotente(scenario) -> None:
    """Um nó que drena o spool depois de uma queda reenvia a mesma seq.

    A restrição UNIQUE (node_id, seq) tem de absorver isso silenciosamente: sem ela a
    série ganharia pontos duplicados a cada reconexão, e a completude passaria de 100%.
    """
    with abrir_sessao() as session:
        primeiro = gravar(session, decodificar(message(7)))
    with abrir_sessao() as session:
        de_novo = gravar(session, decodificar(message(7)))

    assert primeiro.stored
    assert not de_novo.stored
    assert de_novo.duplicate

    with abrir_sessao() as session:
        assert len(list(session.scalars(select(Medicao)))) == 1


def test_no_desconhecido_e_autocadastrado(db) -> None:
    """Telemetria válida de um nó não cadastrado não pode ser perdida."""
    with abrir_sessao() as session:
        resultado = gravar(session, decodificar(message(1, node_id="FFFFAA01")))

    assert resultado.stored
    # Sem colmeia ainda: alguém precisa vinculá-lo pela tela de cadastros. Mas a
    # leitura já está guardada, que é o que importa em campo.
    assert resultado.hive_id is None

    with abrir_sessao() as session:
        no = session.scalar(select(No).where(No.node_id == "FFFFAA01"))
        assert no is not None
        assert no.organization_id is None
        assert no.last_seen_at is not None


def test_sensor_ausente_grava_null_e_nao_zero(scenario) -> None:
    """A distinção entre "sem sensor" e "leu zero" é o insumo da curadoria."""
    # O campo nao vem com zero nem com null: ele simplesmente nao e montado.
    payload = message(1, flags=["sht_out_fault"], temp_out_c=None)

    with abrir_sessao() as session:
        gravar(session, decodificar(payload))

    with abrir_sessao() as session:
        row = session.scalar(select(Medicao))
        assert row.temp_out_c is None
        assert row.diferencial_termico_c is None
        assert row.quality_flags == "sht_out_fault"


def test_leitura_anterior_a_instalacao_fica_sem_colmeia(scenario) -> None:
    """Uma medição de antes de o nó ser instalado não pertence à colmeia.

    Atribuí-la contaminaria a série com leituras feitas na bancada, ou na caixa
    anterior, antes de o nó chegar àquela colônia.
    """
    antes = scenario.installed_at - timedelta(days=1)

    with abrir_sessao() as session:
        resultado = gravar(session, decodificar(message(1, ts=antes)))

    assert resultado.stored
    assert resultado.hive_id is None


def test_no_remanejado_atribui_pela_data_da_medicao(scenario) -> None:
    """O ponto central do modelo histórico de vínculos.

    Um nó movido da colmeia A para a B não pode fazer a série antiga de A migrar para
    B. E uma mensagem que ficou no spool durante a mudança precisa pousar na colmeia em
    que o nó estava **quando mediu**, não onde ele está agora.
    """
    mudanca = datetime.now(UTC) - timedelta(days=2)

    with abrir_sessao() as session:
        atual = session.scalar(
            select(Vinculo).where(Vinculo.node_id == scenario.node_pk)
        )
        atual.removed_at = mudanca
        session.add(
            Vinculo(
                node_id=scenario.node_pk,
                hive_id=scenario.other_hive_id,
                installed_at=mudanca,
            )
        )

    antiga = mudanca - timedelta(days=5)
    nova = mudanca + timedelta(days=1)

    with abrir_sessao() as session:
        # Mensagem antiga, entregue agora (drenada do spool depois da mudança).
        atrasada = gravar(session, decodificar(message(1, ts=antiga)))
        recente = gravar(session, decodificar(message(2, ts=nova)))

    assert atrasada.hive_id == scenario.hive_id, "leitura antiga fica na colmeia de origem"
    assert recente.hive_id == scenario.other_hive_id, "leitura nova vai para a colmeia atual"


def test_last_seen_usa_a_chegada_e_nao_a_medicao(scenario) -> None:
    """Uma mensagem antiga drenada do spool não significa que o nó está vivo agora."""
    antiga = datetime.now(UTC) - timedelta(days=3)

    with abrir_sessao() as session:
        gravar(session, decodificar(message(1, ts=antiga)))

    with abrir_sessao() as session:
        no = session.scalar(select(No).where(No.node_id == scenario.node_id))
        assert no.last_seen_at > antiga + timedelta(days=2)


def test_recusa_e_registrada_com_motivo(db) -> None:
    with abrir_sessao() as session:
        registrar_recusa(session, "JSON malformado", b'{"schema":', "meliponet/v1/X/telemetry")

    with abrir_sessao() as session:
        recusa = session.scalar(select(Recusa))
        assert recusa.reason == "JSON malformado"
        assert recusa.topic == "meliponet/v1/X/telemetry"
