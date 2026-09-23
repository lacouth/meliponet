"""Decodificacao e validacao das mensagens de telemetria.

A fronteira entre o que chega da rede e o que entra no banco: tudo que passa por aqui
vem de um no em campo e portanto nao e confiavel.

A politica e uma so -- **o motivo da recusa e preservado**, nunca descartado em
silencio. Mensagem invalida vira um :class:`ErroDeTelemetria`, que quem chamou grava em
``ingest_rejects``. Os nomes dos campos sao os do contrato.
"""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

#: Raiz do monorepo, para achar ``contracts/``. O contrato e compartilhado com o
#: firmware e por isso vive fora do pacote da plataforma.
PASTA_DOS_CONTRATOS = Path(__file__).resolve().parents[3] / "contracts"

SCHEMA_ID = "meliponet.telemetry.v1"

#: Limite de tamanho do payload. Uma mensagem valida do no completo fica em ~350
#: bytes; qualquer coisa muito maior indica lixo ou um cliente que nao e nosso, e nao
#: vale o custo de tentar parsear.
LIMITE_DE_BYTES = 4096


class ErroDeTelemetria(ValueError):
    """Mensagem que nao pode ser aceita, com o motivo que sera persistido."""

    def __init__(self, motivo: str) -> None:
        super().__init__(motivo)
        self.motivo = motivo


def _agora() -> datetime:
    """O instante atual, em UTC. Serve de valor padrao para ``received_at``."""
    return datetime.now(UTC)


@dataclass
class Telemetria:
    """Uma leitura validada, pronta para persistencia."""

    node_id: str
    seq: int
    #: Instante da *medicao*, pelo relogio do no.
    ts: datetime
    #: Instante da *chegada*, pelo relogio do servidor.
    #:
    #: Os dois sao distintos e a diferenca e informacao: uma mensagem drenada do spool
    #: apos uma queda de rede chega horas depois de ter sido medida.
    #:
    #: `default_factory` diz ao dataclass qual funcao chamar para obter o valor padrao
    #: *a cada leitura nova*. Um `= _agora()` simples seria calculado uma vez so, quando
    #: o modulo carrega, e toda leitura ficaria com o mesmo horario de chegada.
    received_at: datetime = field(default_factory=_agora)
    metrics: dict[str, float] = field(default_factory=dict)
    flags: tuple[str, ...] = ()
    gateway_id: str | None = None

    @property
    def atraso_de_transito(self) -> timedelta:
        """Quanto tempo a leitura levou entre ser medida e chegar."""
        return self.received_at - self.ts

    @property
    def diferencial_termico_c(self) -> float | None:
        """Diferenca entre temperatura interna e externa, em graus Celsius.

        E a estimativa do esforco termorregulatorio da colonia -- a metrica central
        do Edital 17 -- e so existe quando os dois SHT30 responderam.
        """
        dentro = self.metrics.get("temp_in_c")
        fora = self.metrics.get("temp_out_c")
        if dentro is None or fora is None:
            return None
        return dentro - fora


def _carregar_validador() -> Draft202012Validator:
    """Le o schema do contrato, confere que ele mesmo e valido, e monta o validador."""
    schema = json.loads((PASTA_DOS_CONTRATOS / "telemetry.v1.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


#: Montado uma vez, quando o modulo e importado: ler e conferir o schema a cada
#: mensagem seria trabalho repetido.
_VALIDADOR = _carregar_validador()


def _descrever(erro: ValidationError) -> str:
    """Traduz o erro do jsonschema numa razao curta e acionavel."""
    if erro.validator == "required":
        return f"campo obrigatorio ausente: {erro.message}"
    if erro.validator == "additionalProperties":
        return f"campo fora do contrato: {erro.message}"
    if erro.validator == "anyOf":
        return "mensagem sem nenhuma metrica de colmeia"

    # O caminho ate o campo com problema: "temp_in_c", ou "flags.0" para a primeira
    # flag. Erro na raiz da mensagem tem caminho vazio, e ai vai so o texto do jsonschema.
    partes = []
    for parte in erro.absolute_path:
        partes.append(str(parte))
    onde = ".".join(partes)
    if onde:
        return f"{onde}: {erro.message}"
    return erro.message


def _onde_esta_o_erro(erro: ValidationError) -> list:
    """O caminho do erro dentro da mensagem, usado para ordenar os erros.

    A mensagem pode ter varios erros ao mesmo tempo, e a recusa cita so um. Sem ordenar,
    seria o primeiro que o validador encontrasse percorrendo o *schema*; ordenando pelo
    caminho, e o que fica mais perto da raiz da *mensagem* -- um campo que falta no topo
    vem antes de um valor errado dentro de ``flags``.
    """
    return list(erro.absolute_path)


#: Campos do contrato que nao sao metricas de serie temporal.
_NAO_SAO_METRICA = ("schema", "node_id", "seq", "ts", "flags", "gateway_id")


def decodificar(payload: bytes | str) -> Telemetria:
    """Valida ``payload`` contra o contrato e devolve a leitura correspondente.

    Levanta :class:`ErroDeTelemetria` com o motivo em qualquer falha.
    """
    if isinstance(payload, bytes):
        if len(payload) > LIMITE_DE_BYTES:
            raise ErroDeTelemetria(
                f"payload de {len(payload)} bytes excede o limite de {LIMITE_DE_BYTES}"
            )
        try:
            payload = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ErroDeTelemetria(f"payload nao e UTF-8 valido: {exc}") from exc

    try:
        mensagem: Any = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ErroDeTelemetria(f"JSON malformado: {exc.msg} na posicao {exc.pos}") from exc

    if not isinstance(mensagem, dict):
        raise ErroDeTelemetria("payload nao e um objeto JSON")

    # Checa a versao antes do schema: um no com firmware de outra versao produz uma
    # cascata de erros de schema pouco informativos, e a causa real e so esta. O `!r`
    # escreve o valor com aspas, para a recusa distinguir o texto "v2" de um campo
    # ausente, que aparece como None.
    versao = mensagem.get("schema")
    if versao != SCHEMA_ID:
        raise ErroDeTelemetria(f"versao de schema nao suportada: {versao!r}")

    erros = sorted(_VALIDADOR.iter_errors(mensagem), key=_onde_esta_o_erro)
    if erros:
        raise ErroDeTelemetria(_descrever(erros[0]))

    # O ``format: date-time`` do JSON Schema e anotacao, nao validacao: o jsonschema
    # so o verifica com um FormatChecker e a dependencia rfc3339-validator instalada.
    # Por isso o instante e parseado explicitamente aqui, e nao delegado ao schema.
    try:
        ts = datetime.fromisoformat(mensagem["ts"])
    except ValueError as exc:
        raise ErroDeTelemetria(f"ts nao e um instante RFC 3339 valido: {exc}") from exc
    if ts.tzinfo is None:
        raise ErroDeTelemetria("ts sem fuso horario: o contrato exige UTC explicito")

    # Tudo que nao e cabecalho da mensagem e metrica de serie temporal.
    metricas = {}
    for campo, valor in mensagem.items():
        if campo not in _NAO_SAO_METRICA:
            metricas[campo] = valor

    return Telemetria(
        node_id=mensagem["node_id"],
        seq=mensagem["seq"],
        ts=ts.astimezone(UTC),
        metrics=metricas,
        flags=tuple(mensagem.get("flags", ())),
        gateway_id=mensagem.get("gateway_id"),
    )
