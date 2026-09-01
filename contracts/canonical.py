"""Codificacao canonica da telemetria MelipoNet v1.

O firmware C++, o simulador e o ingestor precisam produzir *exatamente* os mesmos
bytes para a mesma leitura. Sem uma regra canonica explicita, a comparacao com os
vetores dourados quebraria por diferencas de arredondamento, de ordem de chaves ou de
espacamento -- sem que nenhum dos lados esteja de fato errado.

Decisao central: **a representacao interna de cada metrica e um inteiro escalado**.
Temperatura trafega em centesimos de grau, peso em gramas, e assim por diante,
conforme :data:`DECIMALS`. A serializacao apenas insere a virgula decimal no inteiro.

Isso importa porque a alternativa -- deixar cada lado formatar um ``float`` com
``%.2f`` -- e traicoeira: a ``printf`` da newlib do ESP32 nao tem o mesmo
arredondamento correto da glibc, o ESP32 calcula em ``float`` de 32 bits onde o
Python usa ``double``, e casos de empate como 30.125 caem para lados diferentes. Com
inteiros escalados o arredondamento acontece **uma vez**, na camada de sensores, e
passa a ser parte da medicao em vez de um detalhe do encoder. E o mesmo inteiro que o
quadro binario LoRa da Fase 5 vai carregar, de modo que os dois transportes rendem
valores identicos.

As demais regras:

1. JSON compacto: sem espacos, separadores ``,`` e ``:``.
2. Ordem de chaves fixa (:data:`FIELD_ORDER`), logica e nao alfabetica. Chaves
   ausentes sao omitidas, nunca emitidas como ``null``.
3. Casas decimais fixas: 12,5 kg sai como ``12.500``, nunca ``12.5``.
4. Flags em ordem canonica (:data:`FLAG_ORDER`), para que a comparacao nao dependa da
   ordem em que o firmware detectou cada condicao.

O lado C++ espelha estas regras em ``firmware/lib/MelipoNet/TelemetryCodec``.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

SCHEMA_ID = "meliponet.telemetry.v1"

#: Ordem de serializacao das chaves. Campos fora desta lista sao rejeitados.
FIELD_ORDER: tuple[str, ...] = (
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
    "snr",
    "sound_rms",
    "sound_bands",
    "gateway_id",
    "flags",
)

#: Casas decimais fixas por campo, equivalentes ao fator de escala do inteiro interno.
#: ``weight_kg`` com 3 casas significa que o inteiro e o peso em gramas.
DECIMALS: Mapping[str, int] = {
    "temp_in_c": 2,
    "temp_out_c": 2,
    "rh_in_pct": 2,
    "rh_out_pct": 2,
    "weight_kg": 3,
    "vbat_v": 2,
    "snr": 1,
    "sound_rms": 1,
    "sound_bands": 1,
}

#: Campos inteiros ja na unidade final (escala 1).
INTEGERS: frozenset[str] = frozenset({"seq", "rssi"})

#: Campos de texto simples.
STRINGS: frozenset[str] = frozenset({"schema", "node_id", "ts", "gateway_id"})

#: Campos cujo valor e uma lista de numeros.
ARRAYS: frozenset[str] = frozenset({"sound_bands"})

#: Ordem canonica das flags.
FLAG_ORDER: tuple[str, ...] = (
    "sht_in_fault",
    "sht_out_fault",
    "hx711_fault",
    "mic_fault",
    "low_batt",
    "clock_unsynced",
    "spooled",
)


def quantize(field: str, value: float) -> int:
    """Converte ``value`` no inteiro escalado canonico de ``field``.

    A regra e: **multiplique em ponto flutuante de dupla precisao, depois arredonde o
    produto com empate para longe do zero.** Nessa ordem, e nao arredondando o valor
    original com aritmetica decimal exata.

    A ordem importa e a escolha e deliberada. Arredondar o valor original seria mais
    "correto" numericamente, mas nao e reproduzivel em C++: para reproduzi-la o firmware
    precisaria da expansao decimal exata do double, que o ESP32 nao tem como calcular
    barato. Ja esta regra e exatamente ``llround(value * 10^places)`` em C -- uma linha,
    identica bit a bit, porque as duas linguagens fazem a mesma multiplicacao IEEE 754 e
    arredondam o mesmo produto do mesmo jeito.

    A diferenca entre as duas ordens nao e teorica: em ~23% dos valores da forma x.xx5 o
    produto em ponto flutuante cai do outro lado do empate. Sem fixar a ordem, firmware
    e simulador produziriam inteiros diferentes para a mesma leitura, e a divergencia so
    apareceria em algumas leituras especificas -- o pior tipo de bug.

    Levanta ``ValueError`` para NaN e infinito: um sensor com falha deve omitir o campo e
    sinalizar a flag correspondente, nunca emitir um valor nao finito.
    """
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"valor nao finito em {field}: omita o campo e sinalize a falha")
    if field in INTEGERS:
        places = 0
    else:
        places = DECIMALS.get(field, -1)
        if places < 0:
            raise ValueError(f"campo numerico sem escala canonica definida: {field}")

    # O produto e calculado em double, como o C++ fara; so entao ele e arredondado.
    # Decimal(produto) e exato, e ROUND_HALF_UP sobre ele equivale a llround.
    product = number * (10.0**places)
    if not math.isfinite(product):
        raise ValueError(f"escala estoura a faixa em {field}: {number}")
    return int(Decimal(product).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def render_scaled(field: str, scaled: int) -> str:
    """Renderiza o inteiro escalado de ``field`` como numero JSON.

    Esta e a unica operacao que o codec C++ precisa reproduzir, e ela e puramente
    inteira -- dai a garantia de igualdade byte a byte entre as duas implementacoes.
    """
    places = 0 if field in INTEGERS else DECIMALS[field]
    if places == 0:
        return str(scaled)
    sign = "-" if scaled < 0 else ""
    digits = str(abs(scaled)).rjust(places + 1, "0")
    whole, fraction = digits[:-places], digits[-places:]
    if sign and int(digits) == 0:
        sign = ""  # nao emite zero negativo
    return f"{sign}{whole}.{fraction}"


def _encode(field: str, value: Any) -> str:
    if field in STRINGS:
        return json.dumps(value, ensure_ascii=True)
    if field == "flags":
        ordered = sorted(value, key=FLAG_ORDER.index)
        return "[" + ",".join(json.dumps(flag) for flag in ordered) + "]"
    if field in ARRAYS:
        return "[" + ",".join(render_scaled(field, quantize(field, item)) for item in value) + "]"
    return render_scaled(field, quantize(field, value))


def canonical_dumps(message: Mapping[str, Any]) -> str:
    """Serializa ``message`` na forma canonica exata que o firmware deve produzir."""
    unknown = set(message) - set(FIELD_ORDER)
    if unknown:
        raise ValueError(f"campos fora do contrato: {sorted(unknown)}")

    parts = [
        f"{json.dumps(field)}:{_encode(field, message[field])}"
        for field in FIELD_ORDER
        if message.get(field) is not None
    ]
    return "{" + ",".join(parts) + "}"


def canonical_loads(text: str) -> dict[str, Any]:
    """Decodifica uma mensagem canonica. Inverso de :func:`canonical_dumps`."""
    return json.loads(text)


def scaled_message(message: Mapping[str, Any]) -> dict[str, Any]:
    """Devolve ``message`` com cada metrica trocada pelo seu inteiro escalado.

    E o formato que o firmware manipula internamente, e o que o gerador de vetores
    grava no cabecalho C++ para que o teste nativo alimente o codec exatamente com os
    mesmos inteiros que o Python usou.
    """
    out: dict[str, Any] = {}
    for field in FIELD_ORDER:
        if message.get(field) is None:
            continue
        value = message[field]
        if field in STRINGS or field == "flags":
            out[field] = value
        elif field in ARRAYS:
            out[field] = [quantize(field, item) for item in value]
        else:
            out[field] = quantize(field, value)
    return out
