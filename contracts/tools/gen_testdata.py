#!/usr/bin/env python3
"""Gera os vetores dourados de ``contracts/testdata/``.

Os vetores sao o unico ponto de acordo entre o firmware C++ e a plataforma Python:
o teste nativo do PlatformIO serializa cada caso em C++ e compara com o arquivo, e o
``pytest`` valida o mesmo arquivo contra o JSON Schema e o decodifica. Divergencia
entre as duas implementacoes quebra o CI antes de chegar ao campo.

Sao gravados tres tipos de artefato:

``testdata/telemetry_*.json``
    Mensagens validas na forma canonica, uma por caso.
``testdata/invalid/*.json`` + ``*.reason``
    Payloads que o ingestor deve rejeitar, com o motivo esperado ao lado, para que o
    teste verifique *por que* foi rejeitado e nao apenas *que* foi.
``testdata/vectors.h``
    Os mesmos casos validos como inteiros escalados mais o JSON esperado, para o teste
    nativo do PlatformIO. Gerado a partir da mesma fonte que os ``.json``, de modo que
    os dois lados nao possam divergir por um vetor ter sido atualizado sem o outro.

Cada arquivo e gravado com uma quebra de linha final, por conveniencia de diff e de
editor; os dois lados removem espacos das pontas antes de comparar.

Uso::

    python3 tools/gen_testdata.py          # regrava os vetores
    python3 tools/gen_testdata.py --check  # falha se algum vetor estiver desatualizado
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from canonical import (
    ARRAYS,
    SCHEMA_ID,
    STRINGS,
    canonical_dumps,
    scaled_message,
)

TESTDATA = Path(__file__).resolve().parent.parent / "testdata"


#: Campos que o contrato sempre exige, e que portanto nao precisam de bit de presenca.
REQUIRED: frozenset[str] = frozenset({"schema", "node_id", "seq", "ts"})


def _base(node_id: str, seq: int, ts: str) -> dict:
    return {"schema": SCHEMA_ID, "node_id": node_id, "seq": seq, "ts": ts}


#: Casos validos. Devem cobrir o prototipo (Fase 3) e o no completo (Fase 5), de modo
#: que a expansao do hardware nao exija nova versao do contrato.
VALID: dict[str, dict] = {
    "01_nominal": {
        **_base("A4C1380F", 10432, "2027-03-14T12:05:00Z"),
        "temp_in_c": 30.12,
        "temp_out_c": 34.8,
        "rh_in_pct": 68.4,
        "rh_out_pct": 41.2,
        "weight_kg": 12.483,
        "vbat_v": 3.92,
        "rssi": -58,
    },
    # Casos de empate e de zero negativo: 30.125 e exatamente representavel e cai no
    # meio, -0.004 arredonda para zero e nao pode sair como "-0.00", e 12.5 kg precisa
    # sair como "12.500" nos dois lados.
    "02_arredondamento": {
        **_base("A4C1380F", 10433, "2027-03-14T12:10:00Z"),
        "temp_in_c": 30.125,
        "temp_out_c": -0.004,
        "rh_in_pct": 99.999,
        "rh_out_pct": 0.0,
        "weight_kg": 12.5,
        "vbat_v": 4.0,
        "rssi": -58,
    },
    # SHT30 externo ausente ou travado: os campos externos somem e a flag explica.
    "03_sht_externo_ausente": {
        **_base("A4C1380F", 10434, "2027-03-14T12:15:00Z"),
        "temp_in_c": 29.87,
        "rh_in_pct": 70.1,
        "weight_kg": 12.481,
        "vbat_v": 3.91,
        "rssi": -61,
        "flags": ["sht_out_fault"],
    },
    # Mensagem que ficou no spool durante uma queda de WiFi, com relogio nao
    # sincronizado e bateria baixa. Ordem das flags deliberadamente fora da canonica.
    "04_spool_relogio_bateria": {
        **_base("7B21C904", 512, "2027-03-14T03:40:00Z"),
        "temp_in_c": 28.4,
        "temp_out_c": 22.15,
        "rh_in_pct": 74.0,
        "rh_out_pct": 88.6,
        "weight_kg": 11.902,
        "vbat_v": 3.41,
        "flags": ["spooled", "low_batt", "clock_unsynced"],
    },
    # Minimo aceitavel: so peso. Exercita a regra "ao menos uma metrica".
    "05_somente_peso": {
        **_base("7B21C904", 513, "2027-03-14T03:45:00Z"),
        "weight_kg": 11.9,
        "flags": ["sht_in_fault", "sht_out_fault"],
    },
    # Deriva de tara produz peso levemente negativo: aceito pelo contrato e tratado
    # na curadoria, em vez de descartado silenciosamente pelo firmware.
    "06_tara_negativa": {
        **_base("7B21C904", 514, "2027-03-14T03:50:00Z"),
        "temp_in_c": 28.31,
        "weight_kg": -0.012,
        "vbat_v": 3.4,
        "flags": ["low_batt"],
    },
    # No completo da Fase 5, chegando por gateway LoRa: acustica, snr e gateway_id.
    "07_no_completo_lora": {
        **_base("C1090E22", 88291, "2027-06-02T15:00:00Z"),
        "temp_in_c": 31.44,
        "temp_out_c": 38.9,
        "rh_in_pct": 62.75,
        "rh_out_pct": 28.3,
        "weight_kg": 18.207,
        "vbat_v": 4.05,
        "rssi": -104,
        "snr": 7.5,
        "sound_rms": 1820.0,
        "sound_bands": [412.0, 980.5, 233.25, 61.0],
        "gateway_id": "gw-jp-01",
    },
}

#: Casos que o ingestor precisa rejeitar. Nao sao produzidos pelo firmware -- servem
#: para provar que a validacao da plataforma nao aceita lixo, e cada um vem com o
#: motivo esperado para que o teste verifique a mensagem, nao so a rejeicao.
INVALID: dict[str, tuple[str, str]] = {
    "01_sem_seq": (
        '{"schema":"meliponet.telemetry.v1","node_id":"A4C1380F","ts":"2027-03-14T12:05:00Z","temp_in_c":30.12}',
        "campo obrigatorio 'seq' ausente",
    ),
    "02_node_id_invalido": (
        '{"schema":"meliponet.telemetry.v1","node_id":"a4c1380f","seq":1,"ts":"2027-03-14T12:05:00Z","temp_in_c":30.12}',
        "node_id deve ser hexadecimal maiusculo de 8 digitos",
    ),
    "03_sem_metrica": (
        '{"schema":"meliponet.telemetry.v1","node_id":"A4C1380F","seq":1,"ts":"2027-03-14T12:05:00Z","vbat_v":3.9}',
        "mensagem sem nenhuma metrica de colmeia",
    ),
    "04_temperatura_fora_de_faixa": (
        '{"schema":"meliponet.telemetry.v1","node_id":"A4C1380F","seq":1,"ts":"2027-03-14T12:05:00Z","temp_in_c":180.0}',
        "temp_in_c acima do limite fisico do SHT30",
    ),
    "05_campo_desconhecido": (
        '{"schema":"meliponet.telemetry.v1","node_id":"A4C1380F","seq":1,"ts":"2027-03-14T12:05:00Z","temp_in_c":30.12,"temp_brood_c":31.0}',
        "campo fora do contrato",
    ),
    "06_schema_errado": (
        '{"schema":"meliponet.telemetry.v2","node_id":"A4C1380F","seq":1,"ts":"2027-03-14T12:05:00Z","temp_in_c":30.12}',
        "versao de schema nao suportada",
    ),
    "07_flag_desconhecida": (
        '{"schema":"meliponet.telemetry.v1","node_id":"A4C1380F","seq":1,"ts":"2027-03-14T12:05:00Z","temp_in_c":30.12,"flags":["queen_lost"]}',
        "flag fora do vocabulario do contrato",
    ),
    "08_json_malformado": (
        '{"schema":"meliponet.telemetry.v1","node_id":"A4C1380F","seq":1,',
        "JSON malformado",
    ),
}


def _cpp_literal(field: str, value) -> str:
    """Traduz um campo ja escalado para o literal C++ correspondente."""
    if field in STRINGS:
        return f'"{value}"'
    if field in ARRAYS:
        return "{" + ", ".join(str(item) for item in value) + "}"
    if field == "flags":
        return " | ".join(f"Flag::{flag}" for flag in value) or "Flag::none"
    return str(value)


def render_header() -> str:
    """Monta ``testdata/vectors.h`` com os casos validos para o teste nativo C++."""
    lines = [
        "// GERADO POR contracts/tools/gen_testdata.py -- NAO EDITE A MAO.",
        "//",
        "// Cada vetor traz as metricas ja como inteiros escalados (a representacao",
        "// interna canonica do contrato) e o JSON exato que o codec deve produzir.",
        "// Rode `python3 contracts/tools/gen_testdata.py` apos alterar o contrato.",
        "#pragma once",
        "",
        '#include "TelemetryCodec.h"',
        "",
        "namespace meliponet {",
        "namespace testdata {",
        "",
        "struct Vector {",
        "  const char *name;",
        "  Telemetry telemetry;",
        "  const char *expected_json;",
        "};",
        "",
        "inline const Vector kVectors[] = {",
    ]

    for name, message in VALID.items():
        scaled = scaled_message(message)
        lines.append("    {")
        lines.append(f'        "{name}",')
        lines.append("        Telemetry{")
        for field, value in scaled.items():
            if field == "schema":
                continue  # constante do contrato, preenchida pelo proprio codec
            lines.append(f"            .{field} = {_cpp_literal(field, value)},")
        # node_id, seq e ts sao obrigatorios pelo contrato; o bitmask de presenca
        # cobre apenas os campos opcionais, que sao os que podem ou nao ser emitidos.
        optional = [f for f in scaled if f not in REQUIRED and f != "flags"]
        present = " | ".join(f"Field::{f}" for f in optional) or "Field::none"
        lines.append(f"            .present = {present},")
        lines.append("        },")
        lines.append(f"        {_json_literal(canonical_dumps(message))},")
        lines.append("    },")

    lines += [
        "};",
        "",
        "inline constexpr size_t kVectorCount = sizeof(kVectors) / sizeof(kVectors[0]);",
        "",
        "}  // namespace testdata",
        "}  // namespace meliponet",
        "",
    ]
    return "\n".join(lines)


def _json_literal(text: str) -> str:
    """Escapa o JSON esperado como literal de string C++."""
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def build() -> dict[Path, str]:
    files: dict[Path, str] = {}
    for name, message in VALID.items():
        files[TESTDATA / f"telemetry_{name}.json"] = canonical_dumps(message) + "\n"
    for name, (payload, reason) in INVALID.items():
        files[TESTDATA / "invalid" / f"{name}.json"] = payload + "\n"
        files[TESTDATA / "invalid" / f"{name}.reason"] = reason + "\n"
    files[TESTDATA / "vectors.h"] = render_header()
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="apenas verifica, nao grava")
    args = parser.parse_args()

    stale = []
    for path, content in build().items():
        current = path.read_text() if path.exists() else None
        if current == content:
            continue
        if args.check:
            stale.append(path)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            print(f"gravado {path.relative_to(TESTDATA.parent)}")

    if stale:
        print("vetores dourados desatualizados:", file=sys.stderr)
        for path in stale:
            print(f"  {path.relative_to(TESTDATA.parent)}", file=sys.stderr)
        print("rode: python3 contracts/tools/gen_testdata.py", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
