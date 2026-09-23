"""Persistencia das leituras validadas.

Fica entre :mod:`meliponet.ingestao.telemetria`, que valida o contrato, e o banco. E
aqui que uma leitura ganha a colmeia a que pertence e que o reenvio de spool e
absorvido.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from meliponet.ingestao.telemetria import Telemetria
from meliponet.modelos import Medicao, No, Recusa, Vinculo

#: Quanto do payload recusado guardar. Suficiente para diagnosticar, pequeno o bastante
#: para que uma enxurrada de lixo nao encha o banco.
LIMITE_DO_PAYLOAD_RECUSADO = 500

#: Metricas do contrato que viram colunas da medicao.
CAMPOS_DE_METRICA = (
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
class ResultadoDaGravacao:
    stored: bool
    #: Verdadeiro quando a leitura ja existia -- reenvio de spool, nao erro.
    duplicate: bool = False
    measurement_id: int | None = None
    hive_id: int | None = None


def no_conhecido(session: Session, node_id: str) -> No:
    """Devolve o no, cadastrando-o automaticamente na primeira aparicao.

    Auto-cadastro e a escolha certa aqui: um no que chega do campo com dados validos
    nao deve ter suas leituras descartadas so porque ninguem o cadastrou antes. Ele
    entra sem organizacao e sem colmeia, aparece na tela de administracao como
    pendente, e suas leituras ja ficam guardadas -- passando a alimentar os graficos
    assim que alguem o vincular.
    """
    no = session.scalar(select(No).where(No.node_id == node_id))
    if no is None:
        no = No(node_id=node_id, label=f"Auto-cadastrado {node_id}")
        session.add(no)
        session.flush()
    return no


def colmeia_no_instante(session: Session, no: No, quando: datetime) -> int | None:
    """Descobre em que colmeia o no estava **no instante da medicao**.

    Nao no instante atual. A diferenca aparece em dois casos reais e e justamente o
    motivo de ``node_assignments`` existir:

    * Um no remanejado de uma colmeia para outra. Resolver pelo estado atual atribuiria
      toda a serie historica da colmeia antiga a nova, corrompendo as duas.
    * Uma mensagem que ficou dias no spool durante uma queda de rede. Ela precisa
      pousar na colmeia em que o no estava quando mediu, nao onde ele esta hoje.
    """
    vinculo = session.scalar(
        select(Vinculo)
        .where(
            Vinculo.node_id == no.id,
            Vinculo.installed_at <= quando,
        )
        .order_by(Vinculo.installed_at.desc())
        .limit(1)
    )
    if vinculo is None or not vinculo.cobre(quando):
        return None
    return vinculo.hive_id


def gravar(session: Session, telemetria: Telemetria) -> ResultadoDaGravacao:
    """Grava ``telemetria``. Reenvio de uma leitura ja conhecida e ignorado."""
    no = no_conhecido(session, telemetria.node_id)

    ja_existe = session.scalar(
        select(Medicao.id).where(
            Medicao.node_id == telemetria.node_id, Medicao.seq == telemetria.seq
        )
    )
    if ja_existe is not None:
        return ResultadoDaGravacao(stored=False, duplicate=True, measurement_id=ja_existe)

    hive_id = colmeia_no_instante(session, no, telemetria.ts)

    medicao = Medicao(
        time=telemetria.ts,
        node_id=telemetria.node_id,
        hive_id=hive_id,
        seq=telemetria.seq,
        gateway_id=telemetria.gateway_id,
        quality_flags=",".join(telemetria.flags) or None,
        **{
            nome: telemetria.metrics[nome]
            for nome in CAMPOS_DE_METRICA
            if nome in telemetria.metrics
        },
    )
    session.add(medicao)

    # `last_seen_at` e o horario de chegada, nao o da medicao: uma mensagem antiga
    # drenada do spool nao significa que o no esta vivo agora.
    no.last_seen_at = telemetria.received_at

    try:
        session.flush()
    except IntegrityError:
        # Duas mensagens com a mesma seq chegando quase juntas -- o SELECT acima nao as
        # separa. A restricao UNIQUE e a autoridade final; aqui so a tratamos como o
        # que ela e: um reenvio, nao um erro.
        session.rollback()
        return ResultadoDaGravacao(stored=False, duplicate=True)

    return ResultadoDaGravacao(stored=True, measurement_id=medicao.id, hive_id=hive_id)


def registrar_recusa(
    session: Session,
    motivo: str,
    payload: bytes | str,
    origem: str | None,
    node_id: str | None = None,
) -> None:
    """Registra uma mensagem recusada, para os indicadores de qualidade do Edital 17."""
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8", errors="replace")

    session.add(
        Recusa(
            topic=origem,
            node_id=node_id,
            reason=motivo,
            payload=payload[:LIMITE_DO_PAYLOAD_RECUSADO],
        )
    )
