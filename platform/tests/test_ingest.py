"""Testes da ingestao: da mensagem MQTT ate a linha no banco."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from meliponet.db import session_scope
from meliponet.ingest.store import record_reject, store
from meliponet.ingest.telemetry import decode
from meliponet.models import IngestReject, Measurement, Node, NodeAssignment
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
    with session_scope() as session:
        result = store(session, decode(message(1)))

    assert result.stored
    assert result.hive_id == scenario.hive_id

    with session_scope() as session:
        row = session.scalar(select(Measurement))
        assert row.temp_in_c == pytest.approx(30.1)
        assert row.thermal_differential_c == pytest.approx(-4.1)


def test_reenvio_do_spool_e_idempotente(scenario) -> None:
    """Um nó que drena o spool depois de uma queda reenvia a mesma seq.

    A restrição UNIQUE (node_id, seq) tem de absorver isso silenciosamente: sem ela a
    série ganharia pontos duplicados a cada reconexão, e a completude passaria de 100%.
    """
    with session_scope() as session:
        first = store(session, decode(message(7)))
    with session_scope() as session:
        again = store(session, decode(message(7)))

    assert first.stored
    assert not again.stored
    assert again.duplicate

    with session_scope() as session:
        assert len(list(session.scalars(select(Measurement)))) == 1


def test_no_desconhecido_e_autocadastrado(db) -> None:
    """Telemetria válida de um nó não cadastrado não pode ser perdida."""
    with session_scope() as session:
        result = store(session, decode(message(1, node_id="FFFFAA01")))

    assert result.stored
    # Sem colmeia ainda: alguém precisa vinculá-lo pela tela de cadastros. Mas a
    # leitura já está guardada, que é o que importa em campo.
    assert result.hive_id is None

    with session_scope() as session:
        node = session.scalar(select(Node).where(Node.node_id == "FFFFAA01"))
        assert node is not None
        assert node.organization_id is None
        assert node.last_seen_at is not None


def test_sensor_ausente_grava_null_e_nao_zero(scenario) -> None:
    """A distinção entre "sem sensor" e "leu zero" é o insumo da curadoria."""
    # O campo nao vem com zero nem com null: ele simplesmente nao e montado.
    payload = message(1, flags=["sht_out_fault"], temp_out_c=None)

    with session_scope() as session:
        store(session, decode(payload))

    with session_scope() as session:
        row = session.scalar(select(Measurement))
        assert row.temp_out_c is None
        assert row.thermal_differential_c is None
        assert row.quality_flags == "sht_out_fault"


def test_leitura_anterior_a_instalacao_fica_sem_colmeia(scenario) -> None:
    """Uma medição de antes de o nó ser instalado não pertence à colmeia.

    Atribuí-la contaminaria a série com leituras feitas na bancada, ou na caixa
    anterior, antes de o nó chegar àquela colônia.
    """
    antes = scenario.installed_at - timedelta(days=1)

    with session_scope() as session:
        result = store(session, decode(message(1, ts=antes)))

    assert result.stored
    assert result.hive_id is None


def test_no_remanejado_atribui_pela_data_da_medicao(scenario) -> None:
    """O ponto central do modelo histórico de vínculos.

    Um nó movido da colmeia A para a B não pode fazer a série antiga de A migrar para
    B. E uma mensagem que ficou no spool durante a mudança precisa pousar na colmeia em
    que o nó estava **quando mediu**, não onde ele está agora.
    """
    mudanca = datetime.now(UTC) - timedelta(days=2)

    with session_scope() as session:
        atual = session.scalar(
            select(NodeAssignment).where(NodeAssignment.node_id == scenario.node_pk)
        )
        atual.removed_at = mudanca
        session.add(
            NodeAssignment(
                node_id=scenario.node_pk,
                hive_id=scenario.other_hive_id,
                installed_at=mudanca,
            )
        )

    antiga = mudanca - timedelta(days=5)
    nova = mudanca + timedelta(days=1)

    with session_scope() as session:
        # Mensagem antiga, entregue agora (drenada do spool depois da mudança).
        atrasada = store(session, decode(message(1, ts=antiga)))
        recente = store(session, decode(message(2, ts=nova)))

    assert atrasada.hive_id == scenario.hive_id, "leitura antiga fica na colmeia de origem"
    assert recente.hive_id == scenario.other_hive_id, "leitura nova vai para a colmeia atual"


def test_last_seen_usa_a_chegada_e_nao_a_medicao(scenario) -> None:
    """Uma mensagem antiga drenada do spool não significa que o nó está vivo agora."""
    antiga = datetime.now(UTC) - timedelta(days=3)

    with session_scope() as session:
        store(session, decode(message(1, ts=antiga)))

    with session_scope() as session:
        node = session.scalar(select(Node).where(Node.node_id == scenario.node_id))
        assert node.last_seen_at > antiga + timedelta(days=2)


def test_recusa_e_registrada_com_motivo(db) -> None:
    with session_scope() as session:
        record_reject(session, "JSON malformado", b'{"schema":', "meliponet/v1/X/telemetry")

    with session_scope() as session:
        reject = session.scalar(select(IngestReject))
        assert reject.reason == "JSON malformado"
        assert reject.topic == "meliponet/v1/X/telemetry"
