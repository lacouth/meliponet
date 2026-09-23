"""Ajudantes para ler os formularios das telas de cadastro.

Existem num arquivo proprio porque as rotas de meliponario, colmeia e no leem os mesmos
tipos de campo, e cada uma escrever o seu jeito de tratar "campo em branco" acabaria em
tres jeitos diferentes.
"""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from flask import request

from meliponet.configuracao import FUSO_DE_EXIBICAO


def texto(campo: str) -> str | None:
    """Le um campo de texto do formulario: vazio vira ``None``, nao string vazia.

    A diferenca importa no banco. String vazia e um valor gravado -- "o municipio e a
    palavra vazia" -- enquanto ``None`` e a ausencia, que e o que um campo deixado em
    branco significa de verdade.
    """
    valor = (request.form.get(campo) or "").strip()
    if not valor:
        return None
    return valor


def decimal(campo: str) -> float | None:
    """Le um campo numerico do formulario. Vazio ou ilegivel vira ``None``."""
    valor = (request.form.get(campo) or "").strip()
    if not valor:
        return None
    try:
        return float(valor)
    except ValueError:
        return None


def ler_instante_local(campo: str) -> datetime | None:
    """Le um ``datetime-local`` do formulario como horario da Paraiba e devolve UTC.

    O campo HTML nao carrega fuso. Interpretar o valor como UTC deslocaria toda
    instalacao em tres horas, e a data de instalacao e o que delimita a que colmeia
    cada leitura pertence.
    """
    valor = request.form.get(campo)
    if not valor:
        return None
    ingenuo = datetime.fromisoformat(valor)
    return ingenuo.replace(tzinfo=ZoneInfo(FUSO_DE_EXIBICAO)).astimezone(UTC)


def escrever_instante_local(valor: datetime | None) -> str:
    """Formata um instante UTC para preencher um ``datetime-local`` do formulario.

    Inverso de ``ler_instante_local``. Sem ele, abrir a tela de edicao mostraria o
    campo de data vazio e salvar apagaria a data que ja estava gravada.
    """
    if valor is None:
        return ""
    return valor.astimezone(ZoneInfo(FUSO_DE_EXIBICAO)).strftime("%Y-%m-%dT%H:%M")
