"""Decodificacao e validacao das mensagens de telemetria recebidas por MQTT.

Esta e a fronteira entre o que chega da rede e o que entra no banco. Tudo que passa
por aqui vem de um no em campo ou de um gateway, e portanto nao e confiavel: pode
estar truncado por um buffer pequeno, vir de um firmware antigo, ou trazer um valor
fisicamente impossivel por causa de um sensor com falha.

A politica de rejeicao segue o Edital 17: **o motivo da rejeicao e preservado**, nunca
descartado em silencio. Uma mensagem invalida vira uma ``TelemetryError`` com uma
razao legivel, que o ingestor grava em ``ingest_rejects`` -- e essa contagem e um dos
indicadores de qualidade que o projeto se compromete a reportar.

Validacao *sintatica* (o que este modulo faz) e diferente de validacao *semantica*
(``meliponet.services.quality``): aqui verificamos que a mensagem obedece ao contrato;
la verificamos se a leitura faz sentido diante do historico daquela colmeia. Uma
leitura semanticamente suspeita e gravada com flag, nao rejeitada.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

#: Raiz do monorepo, para achar ``contracts/``. O contrato e compartilhado com o
#: firmware e por isso vive fora do pacote da plataforma.
CONTRACTS_DIR = Path(__file__).resolve().parents[3] / "contracts"

SCHEMA_ID = "meliponet.telemetry.v1"

#: Limite de tamanho do payload. Uma mensagem valida do no completo fica em ~350
#: bytes; qualquer coisa muito maior indica lixo ou um cliente que nao e nosso, e nao
#: vale o custo de tentar parsear.
MAX_PAYLOAD_BYTES = 4096


class TelemetryError(ValueError):
    """Mensagem que nao pode ser aceita, com o motivo que sera persistido."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class Telemetry:
    """Uma leitura validada, pronta para persistencia."""

    node_id: str
    seq: int
    ts: datetime
    metrics: dict[str, float] = field(default_factory=dict)
    flags: tuple[str, ...] = ()
    gateway_id: str | None = None

    @property
    def thermal_differential_c(self) -> float | None:
        """Diferenca entre temperatura interna e externa, em graus Celsius.

        E a estimativa do esforco termorregulatorio da colonia -- a metrica central
        do Edital 17 -- e so existe quando os dois SHT30 responderam.
        """
        inside = self.metrics.get("temp_in_c")
        outside = self.metrics.get("temp_out_c")
        if inside is None or outside is None:
            return None
        return inside - outside


@lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    schema = json.loads((CONTRACTS_DIR / "telemetry.v1.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _describe(error: ValidationError) -> str:
    """Traduz o erro do jsonschema numa razao curta e acionavel."""
    location = ".".join(str(part) for part in error.absolute_path)
    if error.validator == "required":
        return f"campo obrigatorio ausente: {error.message}"
    if error.validator == "additionalProperties":
        return f"campo fora do contrato: {error.message}"
    if error.validator == "anyOf":
        return "mensagem sem nenhuma metrica de colmeia"
    if location:
        return f"{location}: {error.message}"
    return error.message


#: Campos do contrato que nao sao metricas de serie temporal.
_NON_METRIC = frozenset({"schema", "node_id", "seq", "ts", "flags", "gateway_id"})


def decode(payload: bytes | str) -> Telemetry:
    """Valida ``payload`` contra o contrato e devolve a leitura correspondente.

    Levanta :class:`TelemetryError` com o motivo em qualquer falha.
    """
    if isinstance(payload, bytes):
        if len(payload) > MAX_PAYLOAD_BYTES:
            raise TelemetryError(
                f"payload de {len(payload)} bytes excede o limite de {MAX_PAYLOAD_BYTES}"
            )
        try:
            payload = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise TelemetryError(f"payload nao e UTF-8 valido: {exc}") from exc

    try:
        message: Any = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise TelemetryError(f"JSON malformado: {exc.msg} na posicao {exc.pos}") from exc

    if not isinstance(message, dict):
        raise TelemetryError("payload nao e um objeto JSON")

    # Checa a versao antes do schema: um no com firmware de outra versao produz uma
    # cascata de erros de schema pouco informativos, e a causa real e so esta.
    version = message.get("schema")
    if version != SCHEMA_ID:
        raise TelemetryError(f"versao de schema nao suportada: {version!r}")

    errors = sorted(_validator().iter_errors(message), key=lambda e: list(e.absolute_path))
    if errors:
        raise TelemetryError(_describe(errors[0]))

    # O ``format: date-time`` do JSON Schema e anotacao, nao validacao: o jsonschema
    # so o verifica com um FormatChecker e a dependencia rfc3339-validator instalada.
    # Por isso o instante e parseado explicitamente aqui, e nao delegado ao schema.
    try:
        ts = datetime.fromisoformat(message["ts"])
    except ValueError as exc:
        raise TelemetryError(f"ts nao e um instante RFC 3339 valido: {exc}") from exc
    if ts.tzinfo is None:
        raise TelemetryError("ts sem fuso horario: o contrato exige UTC explicito")

    return Telemetry(
        node_id=message["node_id"],
        seq=message["seq"],
        ts=ts.astimezone(UTC),
        metrics={k: v for k, v in message.items() if k not in _NON_METRIC},
        flags=tuple(message.get("flags", ())),
        gateway_id=message.get("gateway_id"),
    )
