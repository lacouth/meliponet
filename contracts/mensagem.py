"""Monta a mensagem de telemetria do MelipoNet, em Python.

O no sensor produz esta mesma mensagem em C++ -- e escreve-la e o exercicio central do
projeto, descrito em ``firmware/ROTEIRO.md``. Este modulo existe para que o simulador e
os testes da plataforma montem mensagens do mesmo jeito, e para que a ordem dos campos e
o arredondamento tenham um lugar so onde sao decididos.

O que o contrato exige de verdade esta em ``telemetry.v1.schema.json`` e e o que o
ingestor valida. O arredondamento aqui e conveniencia de leitura: a plataforma aceita
qualquer numero dentro da faixa do campo, e o no nao precisa reproduzir byte a byte o que
este arquivo produz.

A regra que vale para os dois lados: **campo ausente e omitido**, nunca enviado como
``null`` nem como zero -- e assim que "o sensor falhou" se distingue de "o sensor leu
zero".
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

#: Versao do contrato. Vai dentro da mensagem, no campo ``schema``.
ESQUEMA = "meliponet.telemetry.v1"

#: Ordem em que os campos sao escritos. Logica, e nao alfabetica: identidade primeiro,
#: depois as grandezas, depois o que descreve a propria transmissao.
ORDEM_DOS_CAMPOS: tuple[str, ...] = (
    "schema",
    "node_id",
    "seq",
    "ts",
    "temp_in_c",
    "temp_out_c",
    "rh_in_pct",
    "rh_out_pct",
    "weight_kg",
    "vbat_v",
    "rssi",
    "flags",
)

#: Quantas casas decimais fazem sentido em cada grandeza. Temperatura e umidade tem
#: resolucao de centesimo no SHT30; a celula de carga, de grama.
CASAS_DECIMAIS: Mapping[str, int] = {
    "temp_in_c": 2,
    "temp_out_c": 2,
    "rh_in_pct": 2,
    "rh_out_pct": 2,
    "weight_kg": 3,
    "vbat_v": 2,
}

#: Condicoes que o proprio no detecta e relata.
FLAGS: tuple[str, ...] = (
    "sht_in_fault",
    "sht_out_fault",
    "hx711_fault",
    "low_batt",
    "clock_unsynced",
    "spooled",
)


def arredondar(campo: str, valor: float) -> float:
    """Arredonda ``valor`` para as casas decimais que o campo comporta."""
    casas = CASAS_DECIMAIS.get(campo)
    if casas is None:
        return valor
    return round(valor, casas)


def serializar(mensagem: Mapping[str, Any]) -> str:
    """Devolve ``mensagem`` como o JSON compacto que o no envia.

    Campos com valor ``None`` e campos fora de :data:`ORDEM_DOS_CAMPOS` nao entram.
    """
    pronta: dict[str, Any] = {}
    for campo in ORDEM_DOS_CAMPOS:
        valor = mensagem.get(campo)
        if valor is None:
            continue
        pronta[campo] = arredondar(campo, valor) if isinstance(valor, float) else valor
    return json.dumps(pronta, separators=(",", ":"), ensure_ascii=True)
