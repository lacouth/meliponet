"""Persistencia das leituras validadas.

Fica entre :mod:`meliponet.ingest.telemetry` (que valida o contrato) e o banco. E aqui
que uma leitura ganha a colmeia a que pertence e que o reenvio de spool e absorvido.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from meliponet.ingest.telemetry import Telemetry
from meliponet.models import IngestReject, Measurement, Node

#: Quanto do payload recusado guardar. Suficiente para diagnosticar, pequeno o bastante
#: para que uma enxurrada de lixo nao encha o banco.
REJECT_PAYLOAD_LIMIT = 500


@dataclass(frozen=True, slots=True)
class StoreResult:
    stored: bool
    #: Verdadeiro quando a leitura ja existia -- reenvio de spool, nao erro.
    duplicate: bool = False
    measurement_id: int | None = None


def _known_node(session: Session, node_id: str) -> Node:
    """Devolve o no, cadastrando-o automaticamente na primeira aparicao.

    Auto-cadastro e a escolha certa para esta fase: um no que chega do campo com dados
    validos nao deve ter suas leituras descartadas so porque ninguem o cadastrou antes.
    Ele fica sem colmeia associada ate que alguem o vincule pela interface, e as
    leituras ja ficam guardadas. A Fase 2, com autenticacao, restringe isso a nos
    previamente autorizados.
    """
    node = session.scalar(select(Node).where(Node.node_id == node_id))
    if node is None:
        node = Node(node_id=node_id, label=f"Auto-cadastrado {node_id}")
        session.add(node)
        session.flush()
    return node


def store(session: Session, telemetry: Telemetry) -> StoreResult:
    """Grava ``telemetry``. Reenvio de uma leitura ja conhecida e ignorado."""
    node = _known_node(session, telemetry.node_id)

    already = session.scalar(
        select(Measurement.id).where(
            Measurement.node_id == telemetry.node_id, Measurement.seq == telemetry.seq
        )
    )
    if already is not None:
        return StoreResult(stored=False, duplicate=True, measurement_id=already)

    measurement = Measurement(
        time=telemetry.ts,
        node_id=telemetry.node_id,
        hive_id=node.hive_id,
        seq=telemetry.seq,
        gateway_id=telemetry.gateway_id,
        quality_flags=",".join(telemetry.flags) or None,
        **{
            name: telemetry.metrics[name]
            for name in (
                "temp_in_c",
                "temp_out_c",
                "rh_in_pct",
                "rh_out_pct",
                "weight_kg",
                "vbat_v",
                "rssi",
                "snr",
                "sound_rms",
            )
            if name in telemetry.metrics
        },
    )
    session.add(measurement)

    node.last_seen_at = datetime.now(UTC)

    try:
        session.flush()
    except IntegrityError:
        # Duas mensagens com a mesma seq chegando quase juntas -- o SELECT acima nao as
        # separa. A restricao UNIQUE e a autoridade final; aqui so a tratamos como o
        # que ela e: um reenvio, nao um erro.
        session.rollback()
        return StoreResult(stored=False, duplicate=True)

    return StoreResult(stored=True, measurement_id=measurement.id)


def record_reject(session: Session, reason: str, payload: bytes | str, topic: str | None) -> None:
    """Registra uma mensagem recusada, para os indicadores de qualidade do Edital 17."""
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8", errors="replace")

    session.add(
        IngestReject(
            topic=topic,
            reason=reason,
            payload=payload[:REJECT_PAYLOAD_LIMIT],
        )
    )
