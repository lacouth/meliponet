"""Persistencia das leituras validadas.

Fica entre :mod:`meliponet.ingest.telemetry`, que valida o contrato, e o banco. E aqui
que uma leitura ganha a colmeia a que pertence e que o reenvio de spool e absorvido.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from meliponet.ingest.telemetry import Telemetry
from meliponet.models import IngestReject, Measurement, Node, NodeAssignment

#: Quanto do payload recusado guardar. Suficiente para diagnosticar, pequeno o bastante
#: para que uma enxurrada de lixo nao encha o banco.
REJECT_PAYLOAD_LIMIT = 500

#: Metricas do contrato que viram colunas da medicao.
METRIC_FIELDS = (
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


@dataclass(frozen=True, slots=True)
class StoreResult:
    stored: bool
    #: Verdadeiro quando a leitura ja existia -- reenvio de spool, nao erro.
    duplicate: bool = False
    measurement_id: int | None = None
    hive_id: int | None = None


def known_node(session: Session, node_id: str) -> Node:
    """Devolve o no, cadastrando-o automaticamente na primeira aparicao.

    Auto-cadastro e a escolha certa aqui: um no que chega do campo com dados validos
    nao deve ter suas leituras descartadas so porque ninguem o cadastrou antes. Ele
    entra sem organizacao e sem colmeia, aparece na tela de administracao como
    pendente, e suas leituras ja ficam guardadas -- passando a alimentar os graficos
    assim que alguem o vincular.
    """
    node = session.scalar(select(Node).where(Node.node_id == node_id))
    if node is None:
        node = Node(node_id=node_id, label=f"Auto-cadastrado {node_id}")
        session.add(node)
        session.flush()
    return node


def resolve_hive(session: Session, node: Node, when: datetime) -> int | None:
    """Descobre em que colmeia o no estava **no instante da medicao**.

    Nao no instante atual. A diferenca aparece em dois casos reais e e justamente o
    motivo de ``node_assignments`` existir:

    * Um no remanejado de uma colmeia para outra. Resolver pelo estado atual atribuiria
      toda a serie historica da colmeia antiga a nova, corrompendo as duas.
    * Uma mensagem que ficou dias no spool durante uma queda de rede. Ela precisa
      pousar na colmeia em que o no estava quando mediu, nao onde ele esta hoje.
    """
    assignment = session.scalar(
        select(NodeAssignment)
        .where(
            NodeAssignment.node_id == node.id,
            NodeAssignment.installed_at <= when,
        )
        .order_by(NodeAssignment.installed_at.desc())
        .limit(1)
    )
    if assignment is None or not assignment.covers(when):
        return None
    return assignment.hive_id


def store(session: Session, telemetry: Telemetry) -> StoreResult:
    """Grava ``telemetry``. Reenvio de uma leitura ja conhecida e ignorado."""
    node = known_node(session, telemetry.node_id)

    already = session.scalar(
        select(Measurement.id).where(
            Measurement.node_id == telemetry.node_id, Measurement.seq == telemetry.seq
        )
    )
    if already is not None:
        return StoreResult(stored=False, duplicate=True, measurement_id=already)

    hive_id = resolve_hive(session, node, telemetry.ts)

    measurement = Measurement(
        time=telemetry.ts,
        node_id=telemetry.node_id,
        hive_id=hive_id,
        seq=telemetry.seq,
        gateway_id=telemetry.gateway_id,
        quality_flags=",".join(telemetry.flags) or None,
        **{
            name: telemetry.metrics[name] for name in METRIC_FIELDS if name in telemetry.metrics
        },
    )
    session.add(measurement)

    # `last_seen_at` e o horario de chegada, nao o da medicao: uma mensagem antiga
    # drenada do spool nao significa que o no esta vivo agora.
    node.last_seen_at = telemetry.received_at

    try:
        session.flush()
    except IntegrityError:
        # Duas mensagens com a mesma seq chegando quase juntas -- o SELECT acima nao as
        # separa. A restricao UNIQUE e a autoridade final; aqui so a tratamos como o
        # que ela e: um reenvio, nao um erro.
        session.rollback()
        return StoreResult(stored=False, duplicate=True)

    return StoreResult(stored=True, measurement_id=measurement.id, hive_id=hive_id)


def record_reject(
    session: Session,
    reason: str,
    payload: bytes | str,
    topic: str | None,
    node_id: str | None = None,
) -> None:
    """Registra uma mensagem recusada, para os indicadores de qualidade do Edital 17."""
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8", errors="replace")

    session.add(
        IngestReject(
            topic=topic,
            node_id=node_id,
            reason=reason,
            payload=payload[:REJECT_PAYLOAD_LIMIT],
        )
    )
