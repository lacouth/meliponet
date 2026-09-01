"""Testes da ingestao: da mensagem MQTT ate a linha no banco."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from canonical import SCHEMA_ID, canonical_dumps
from meliponet.db import create_all, init_engine, session_scope
from meliponet.ingest.store import record_reject, store
from meliponet.ingest.telemetry import decode
from meliponet.models import Apiary, Hive, IngestReject, Measurement, Node
from sqlalchemy import select


@pytest.fixture
def db(tmp_path):
    """Banco isolado por teste, para que um nao enxergue as linhas do outro."""
    engine = init_engine(f"sqlite:///{tmp_path / 'test.sqlite3'}")
    create_all(engine)
    return engine


def message(seq: int, **overrides) -> str:
    payload = {
        "schema": SCHEMA_ID,
        "node_id": "A4C13800",
        "seq": seq,
        "ts": (datetime.now(UTC) - timedelta(minutes=seq)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "temp_in_c": 30.1,
        "temp_out_c": 34.2,
        "weight_kg": 12.4,
        **overrides,
    }
    return canonical_dumps(payload)


def test_grava_leitura(db) -> None:
    with session_scope() as session:
        result = store(session, decode(message(1)))

    assert result.stored
    with session_scope() as session:
        row = session.scalar(select(Measurement))
        assert row.temp_in_c == pytest.approx(30.1)
        assert row.thermal_differential_c == pytest.approx(-4.1)


def test_reenvio_do_spool_e_idempotente(db) -> None:
    """Um nó que drena o spool depois de uma queda reenvia a mesma seq.

    A restrição UNIQUE (node_id, seq) tem de absorver isso silenciosamente: sem ela a
    série ganharia pontos duplicados a cada reconexão, e a contagem de completude
    passaria de 100%.
    """
    with session_scope() as session:
        first = store(session, decode(message(7)))
    with session_scope() as session:
        again = store(session, decode(message(7)))

    assert first.stored
    assert not again.stored
    assert again.duplicate

    with session_scope() as session:
        assert session.scalar(select(Measurement.id).where(Measurement.seq == 7)) is not None
        assert len(list(session.scalars(select(Measurement)))) == 1


def test_no_desconhecido_e_autocadastrado(db) -> None:
    """Telemetria válida de um nó não cadastrado não pode ser perdida."""
    with session_scope() as session:
        store(session, decode(message(1)))

    with session_scope() as session:
        node = session.scalar(select(Node).where(Node.node_id == "A4C13800"))
        assert node is not None
        # Sem colmeia ainda: alguém precisa vinculá-lo pela interface. Mas a leitura
        # já está guardada, que é o que importa em campo.
        assert node.hive_id is None
        assert node.last_seen_at is not None


def test_leitura_segue_a_colmeia_do_no(db) -> None:
    with session_scope() as session:
        apiary = Apiary(name="Meliponário de teste")
        session.add(apiary)
        session.flush()
        hive = Hive(apiary_id=apiary.id, name="Colmeia 01")
        session.add(hive)
        session.flush()
        session.add(Node(node_id="A4C13800", hive_id=hive.id))
        hive_id = hive.id

    with session_scope() as session:
        store(session, decode(message(1)))

    with session_scope() as session:
        assert session.scalar(select(Measurement.hive_id)) == hive_id


def test_sensor_ausente_grava_null_e_nao_zero(db) -> None:
    """A distinção entre "sem sensor" e "leu zero" é o insumo da curadoria."""
    payload = message(1, flags=["sht_out_fault"])
    payload = payload.replace('"temp_out_c":34.20,', "")

    with session_scope() as session:
        store(session, decode(payload))

    with session_scope() as session:
        row = session.scalar(select(Measurement))
        assert row.temp_out_c is None
        assert row.thermal_differential_c is None
        assert row.quality_flags == "sht_out_fault"


def test_recusa_e_registrada_com_motivo(db) -> None:
    with session_scope() as session:
        record_reject(session, "JSON malformado", b'{"schema":', "meliponet/v1/X/telemetry")

    with session_scope() as session:
        reject = session.scalar(select(IngestReject))
        assert reject.reason == "JSON malformado"
        assert reject.topic == "meliponet/v1/X/telemetry"
