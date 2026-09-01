"""Consultas de series temporais que alimentam o dashboard.

A regra que governa este modulo: **a janela pedida escolhe a fonte**. Janelas curtas
leem a tabela bruta; janelas longas leem os agregados continuos do TimescaleDB. Sem
isso, "ultimos 30 dias" de uma colmeia amostrada a cada 5 minutos varreria quase nove
mil pontos por metrica so para desenhar um grafico de algumas centenas de pixels.

Em SQLite os agregados nao existem e a leitura cai sempre na tabela bruta, com um
passo de reamostragem em Python. O resultado e o mesmo; o que muda e onde o trabalho
acontece.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from meliponet.models import Measurement

#: Janelas oferecidas na interface, com o passo de reamostragem de cada uma. O passo e
#: escolhido para render algumas centenas de pontos: o suficiente para o olho, pouco o
#: bastante para a rede rural.
#:
#: Toda janela tem passo, inclusive a de 24 h, cujo passo e o proprio intervalo nominal
#: de amostragem do no. Sem isso, uma mensagem perdida sumiria da serie e o grafico
#: ligaria os dois vizinhos por uma reta -- escondendo exatamente a lacuna que o
#: Edital 17 se propoe a medir.
WINDOWS: dict[str, tuple[str, timedelta, timedelta]] = {
    "24h": ("Últimas 24 horas", timedelta(hours=24), timedelta(minutes=5)),
    "7d": ("Últimos 7 dias", timedelta(days=7), timedelta(minutes=30)),
    "30d": ("Últimos 30 dias", timedelta(days=30), timedelta(hours=2)),
}

DEFAULT_WINDOW = "24h"

METRIC_COLUMNS = (
    "temp_in_c",
    "temp_out_c",
    "rh_in_pct",
    "rh_out_pct",
    "weight_kg",
    "vbat_v",
)


@dataclass(frozen=True, slots=True)
class Point:
    time: datetime
    values: dict[str, float | None]


def _align(when: datetime, step: timedelta) -> datetime:
    """Alinha ``when`` ao inicio do balde de ``step`` contado a partir da epoca.

    Ancorar na epoca, e nao na primeira leitura, mantem os baldes estaveis entre um
    refresh e o seguinte -- caso contrario cada recarga do painel deslocaria levemente
    todos os pontos do grafico.
    """
    seconds = int(step.total_seconds())
    stamp = int(when.timestamp())
    return datetime.fromtimestamp(stamp - stamp % seconds, tz=UTC)


def _resample(
    rows: list[Measurement], step: timedelta, since: datetime, until: datetime
) -> list[Point]:
    """Agrupa leituras em baldes de ``step`` cobrindo toda a janela.

    Percorre **todos** os baldes do intervalo, e nao apenas os que tem leitura. Um
    balde vazio vira um ponto com ``None`` em cada metrica, e nao um ponto ausente:
    ausente faria o Chart.js ligar os vizinhos por uma reta, apagando visualmente a
    perda de mensagens. Zero seria pior ainda, porque viraria um mergulho falso na
    serie. ``None`` e o unico valor que representa "nao sabemos".
    """
    buckets: dict[datetime, list[Measurement]] = {}
    for row in rows:
        buckets.setdefault(_align(row.time, step), []).append(row)

    points = []
    bucket_time = _align(since, step)
    last = _align(until, step)
    while bucket_time <= last:
        members = buckets.get(bucket_time, [])
        values: dict[str, float | None] = {}
        for column in METRIC_COLUMNS:
            present = [getattr(m, column) for m in members if getattr(m, column) is not None]
            values[column] = sum(present) / len(present) if present else None
        points.append(Point(time=bucket_time, values=values))
        bucket_time += step
    return points


def series(session: Session, hive_id: int, window: str = DEFAULT_WINDOW) -> list[Point]:
    """Serie de uma colmeia na janela pedida, ja reamostrada."""
    _, span, step = WINDOWS.get(window, WINDOWS[DEFAULT_WINDOW])
    until = datetime.now(UTC)
    since = until - span

    rows = list(
        session.scalars(
            select(Measurement)
            .where(Measurement.hive_id == hive_id, Measurement.time >= since)
            .order_by(Measurement.time)
        )
    )
    return _resample(rows, step, since, until)


def latest(session: Session, hive_id: int) -> Measurement | None:
    """Leitura mais recente de uma colmeia."""
    return session.scalar(
        select(Measurement)
        .where(Measurement.hive_id == hive_id)
        .order_by(Measurement.time.desc())
        .limit(1)
    )


def completeness(session: Session, hive_id: int, window: str = DEFAULT_WINDOW) -> dict[str, int]:
    """Contagens de completude da janela, base do painel de qualidade da Fase 6.

    ``gaps`` conta os saltos na sequencia ``seq``, que e a medida direta de mensagens
    perdidas -- e nao uma estimativa a partir do intervalo entre horarios.
    """
    _, span, _ = WINDOWS.get(window, WINDOWS[DEFAULT_WINDOW])
    since = datetime.now(UTC) - span

    seqs = list(
        session.scalars(
            select(Measurement.seq)
            .where(Measurement.hive_id == hive_id, Measurement.time >= since)
            .order_by(Measurement.seq)
        )
    )
    if not seqs:
        return {"received": 0, "expected": 0, "gaps": 0}

    expected = seqs[-1] - seqs[0] + 1
    return {"received": len(seqs), "expected": expected, "gaps": expected - len(seqs)}


def hive_count(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(Measurement)) or 0
