"""Verifica que a plataforma le exatamente o contrato que o firmware escreve.

O par deste arquivo e ``firmware/test/native/test_codec/``, que faz o caminho oposto:
serializa em C++ e compara com os mesmos vetores. Enquanto os dois passarem, firmware
e plataforma nao podem ter divergido -- e essa e a unica garantia disso, ja que as
duas implementacoes sao escritas em linguagens diferentes por pessoas diferentes.
"""

from __future__ import annotations

import json
from datetime import UTC
from pathlib import Path

import pytest
from canonical import canonical_dumps, quantize, render_scaled
from meliponet.ingest.telemetry import SCHEMA_ID, TelemetryError, decode

REPO_ROOT = Path(__file__).resolve().parents[2]
TESTDATA = REPO_ROOT / "contracts" / "testdata"

VALID_VECTORS = sorted(TESTDATA.glob("telemetry_*.json"))
INVALID_VECTORS = sorted((TESTDATA / "invalid").glob("*.json"))


def test_ha_vetores_para_testar() -> None:
    # Um glob vazio faria todos os testes parametrizados passarem por vacuidade, que
    # e exatamente o modo como esta protecao poderia falhar silenciosamente.
    assert len(VALID_VECTORS) >= 5
    assert len(INVALID_VECTORS) >= 5


@pytest.mark.parametrize("vector", VALID_VECTORS, ids=lambda p: p.stem)
def test_vetor_valido_e_aceito(vector: Path) -> None:
    telemetry = decode(vector.read_bytes().strip())

    assert telemetry.node_id
    assert telemetry.ts.tzinfo == UTC
    assert telemetry.metrics, "todo vetor valido carrega ao menos uma metrica"


@pytest.mark.parametrize("vector", INVALID_VECTORS, ids=lambda p: p.stem)
def test_vetor_invalido_e_rejeitado_com_motivo(vector: Path) -> None:
    expected_reason = vector.with_suffix(".reason").read_text().strip()

    with pytest.raises(TelemetryError) as excinfo:
        decode(vector.read_bytes().strip())

    # A razao registrada precisa ser util para quem for ler `ingest_rejects` meses
    # depois, entao o teste exige uma mensagem nao vazia e anota a esperada.
    assert excinfo.value.reason, f"rejeicao sem motivo (esperado algo como: {expected_reason})"


@pytest.mark.parametrize("vector", VALID_VECTORS, ids=lambda p: p.stem)
def test_vetor_esta_na_forma_canonica(vector: Path) -> None:
    """Reserializar um vetor tem de devolver os mesmos bytes.

    Isto e o que garante que os arquivos em ``testdata/`` de fato representam o que o
    firmware produz, e nao um JSON equivalente porem diferente byte a byte -- que
    passaria neste conjunto de testes mas falharia no teste nativo em C++.
    """
    raw = vector.read_text().strip()
    message = json.loads(raw)

    assert canonical_dumps(message) == raw


def test_reserializacao_preserva_ordem_das_chaves() -> None:
    # Ordem embaralhada na entrada precisa sair na ordem canonica.
    embaralhado = {
        "weight_kg": 12.483,
        "ts": "2027-03-14T12:05:00Z",
        "node_id": "A4C1380F",
        "schema": SCHEMA_ID,
        "seq": 10432,
    }

    assert canonical_dumps(embaralhado) == (
        '{"schema":"meliponet.telemetry.v1","node_id":"A4C1380F","seq":10432,'
        '"ts":"2027-03-14T12:05:00Z","weight_kg":12.483}'
    )


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        # Empate exato: a regra canonica e ROUND_HALF_UP, e nao o modo de
        # arredondamento da biblioteca C de cada plataforma.
        ("temp_in_c", 30.125, "30.13"),
        ("temp_in_c", 68.4, "68.40"),
        # Casas fixas: 12,5 kg nao pode sair como "12.5".
        ("weight_kg", 12.5, "12.500"),
        # Deriva de tara: peso negativo pequeno preserva o sinal.
        ("weight_kg", -0.012, "-0.012"),
        # ...mas um valor que arredonda para zero nao vira "-0.00".
        ("temp_out_c", -0.004, "0.00"),
        ("rh_in_pct", 99.999, "100.00"),
    ],
)
def test_regra_de_arredondamento(field: str, value: float, expected: str) -> None:
    assert render_scaled(field, quantize(field, value)) == expected


def test_diferencial_termico() -> None:
    telemetry = decode(
        canonical_dumps(
            {
                "schema": SCHEMA_ID,
                "node_id": "A4C1380F",
                "seq": 1,
                "ts": "2027-03-14T12:05:00Z",
                "temp_in_c": 30.12,
                "temp_out_c": 34.8,
            }
        )
    )

    assert telemetry.thermal_differential_c == pytest.approx(-4.68)


def test_diferencial_termico_ausente_sem_sensor_externo() -> None:
    telemetry = decode(
        canonical_dumps(
            {
                "schema": SCHEMA_ID,
                "node_id": "A4C1380F",
                "seq": 1,
                "ts": "2027-03-14T12:05:00Z",
                "temp_in_c": 30.12,
                "flags": ["sht_out_fault"],
            }
        )
    )

    assert telemetry.thermal_differential_c is None
    assert telemetry.flags == ("sht_out_fault",)


def test_payload_gigante_e_rejeitado_sem_parsear() -> None:
    with pytest.raises(TelemetryError, match="excede o limite"):
        decode(b"{" + b"x" * 8192)


def test_ts_sem_fuso_e_rejeitado() -> None:
    # O contrato exige UTC explicito: sem isso, uma leitura de campo entraria no banco
    # com tres horas de erro sem que nada acusasse.
    payload = (
        '{"schema":"meliponet.telemetry.v1","node_id":"A4C1380F","seq":1,'
        '"ts":"2027-03-14T12:05:00","temp_in_c":30.12}'
    )

    with pytest.raises(TelemetryError, match="fuso"):
        decode(payload)
