"""Consultas de serie temporal que alimentam o painel.

A regra que governa este modulo: **a janela pedida escolhe o passo**. Janela curta,
passo curto; janela longa, passo longo -- o suficiente para o olho, pouco o bastante
para a rede rural.

O porque dos baldes vazios virarem ``None`` e nao sumirem esta em
``docs/guia/03-a-plataforma.md``.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from meliponet.modelos import Medicao

#: Janelas oferecidas na interface, com o passo de reamostragem de cada uma.
#:
#: Toda janela tem passo, inclusive a de 24 h, cujo passo e o proprio intervalo nominal
#: de amostragem do no. Sem isso, uma mensagem perdida sumiria da serie e o grafico
#: ligaria os dois vizinhos por uma reta -- escondendo exatamente a lacuna que o
#: Edital 17 se propoe a medir.
JANELAS: dict[str, tuple[str, timedelta, timedelta]] = {
    "24h": ("Últimas 24 horas", timedelta(hours=24), timedelta(minutes=5)),
    "7d": ("Últimos 7 dias", timedelta(days=7), timedelta(minutes=30)),
    "30d": ("Últimos 30 dias", timedelta(days=30), timedelta(hours=2)),
}

JANELA_PADRAO = "24h"

COLUNAS_DE_METRICA = (
    "temp_in_c",
    "temp_out_c",
    "rh_in_pct",
    "rh_out_pct",
    "weight_kg",
    "vbat_v",
)


@dataclass
class Ponto:
    """Um ponto do grafico: o inicio do balde e a media de cada metrica nele."""

    time: datetime
    values: dict[str, float | None]


def _alinhar(quando: datetime, passo: timedelta) -> datetime:
    """Alinha ``quando`` ao inicio do balde de ``passo`` contado a partir da epoca.

    Ancorar na epoca, e nao na primeira leitura, mantem os baldes estaveis entre um
    refresh e o seguinte -- caso contrario cada recarga do painel deslocaria levemente
    todos os pontos do grafico.
    """
    segundos = int(passo.total_seconds())
    carimbo = int(quando.timestamp())
    return datetime.fromtimestamp(carimbo - carimbo % segundos, tz=UTC)


def _reamostrar(
    linhas: list[Medicao], passo: timedelta, desde: datetime, ate: datetime
) -> list[Ponto]:
    """Agrupa leituras em baldes de ``passo`` cobrindo toda a janela.

    Percorre **todos** os baldes do intervalo, e nao apenas os que tem leitura. Um
    balde vazio vira um ponto com ``None`` em cada metrica, e nao um ponto ausente:
    ausente faria o Chart.js ligar os vizinhos por uma reta, apagando visualmente a
    perda de mensagens. Zero seria pior ainda, porque viraria um mergulho falso na
    serie. ``None`` e o unico valor que representa "nao sabemos".
    """
    # Primeiro separa as leituras por balde: a chave e o instante em que o balde comeca.
    baldes: dict[datetime, list[Medicao]] = {}
    for linha in linhas:
        inicio = _alinhar(linha.time, passo)
        if inicio not in baldes:
            baldes[inicio] = []
        baldes[inicio].append(linha)

    # Depois percorre a janela inteira, balde a balde, tenha ele leitura ou nao.
    pontos = []
    balde = _alinhar(desde, passo)
    ultimo = _alinhar(ate, passo)
    while balde <= ultimo:
        medicoes = baldes.get(balde, [])
        valores: dict[str, float | None] = {}
        for coluna in COLUNAS_DE_METRICA:
            valores[coluna] = _media(medicoes, coluna)
        pontos.append(Ponto(time=balde, values=valores))
        balde += passo
    return pontos


def _media(medicoes: list[Medicao], coluna: str) -> float | None:
    """Media de ``coluna`` entre as medicoes do balde, pulando as que nao tem valor.

    Um sensor que falhou deixa a coluna vazia (``None``), e ela fica de fora da conta --
    em vez de entrar como zero e puxar a media para baixo. Se nenhuma medicao tem valor,
    a media tambem e ``None``.
    """
    soma = 0.0
    quantas = 0
    for medicao in medicoes:
        valor = getattr(medicao, coluna)
        if valor is not None:
            soma += valor
            quantas += 1
    if quantas == 0:
        return None
    return soma / quantas


def serie(session: Session, colmeia_id: int, janela: str = JANELA_PADRAO) -> list[Ponto]:
    """Serie de uma colmeia na janela pedida, ja reamostrada."""
    _, duracao, passo = JANELAS.get(janela, JANELAS[JANELA_PADRAO])
    ate = datetime.now(UTC)
    desde = ate - duracao

    linhas = list(
        session.scalars(
            select(Medicao)
            .where(Medicao.hive_id == colmeia_id, Medicao.time >= desde)
            .order_by(Medicao.time)
        )
    )
    return _reamostrar(linhas, passo, desde, ate)


def ultima_leitura(session: Session, colmeia_id: int) -> Medicao | None:
    """Leitura mais recente de uma colmeia."""
    return session.scalar(
        select(Medicao)
        .where(Medicao.hive_id == colmeia_id)
        .order_by(Medicao.time.desc())
        .limit(1)
    )


def completude(session: Session, colmeia_id: int, janela: str = JANELA_PADRAO) -> dict[str, int]:
    """Contagens de completude da janela, base do painel de qualidade da Fase 6.

    ``gaps`` conta os saltos na sequencia ``seq``, que e a medida direta de mensagens
    perdidas -- e nao uma estimativa a partir do intervalo entre horarios.
    """
    _, duracao, _ = JANELAS.get(janela, JANELAS[JANELA_PADRAO])
    desde = datetime.now(UTC) - duracao

    seqs = list(
        session.scalars(
            select(Medicao.seq)
            .where(Medicao.hive_id == colmeia_id, Medicao.time >= desde)
            .order_by(Medicao.seq)
        )
    )
    if not seqs:
        return {"received": 0, "expected": 0, "gaps": 0}

    # `seqs` vem ordenada: a primeira e a menor, e a ultima (`[-1]` conta do fim) a maior.
    # Toda seq entre as duas deveria ter chegado.
    menor = seqs[0]
    maior = seqs[-1]
    esperadas = maior - menor + 1
    recebidas = len(seqs)
    return {"received": recebidas, "expected": esperadas, "gaps": esperadas - recebidas}


def contar_medicoes(session: Session, colmeia_ids: list[int]) -> int:
    """Quantas medicoes existem, somando as colmeias de ``colmeia_ids``."""
    if not colmeia_ids:
        return 0
    total = session.scalar(
        select(func.count()).select_from(Medicao).where(Medicao.hive_id.in_(colmeia_ids))
    )
    # O banco pode devolver None em vez de zero quando nao ha linha nenhuma.
    if total is None:
        return 0
    return total
