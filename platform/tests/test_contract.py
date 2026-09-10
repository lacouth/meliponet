"""Verifica que a plataforma aceita exatamente a mensagem que o roteiro pede.

Os arquivos em ``contracts/exemplos/`` sao o que o aluno le em
``firmware/ROTEIRO.md`` e copia para o firmware dele. Se um deles deixasse de ser
aceito, o roteiro passaria a ensinar uma mensagem que a plataforma recusa -- e o aluno
levaria horas para descobrir que o erro nao era dele. Estes testes existem para que isso
quebre aqui, e nao na bancada.

Os ``invalidas/`` fazem o caminho oposto: garantem que a plataforma recusa, com um
motivo legivel, cada erro que o aluno tem chance de cometer.
"""

from __future__ import annotations

import json
from datetime import UTC
from pathlib import Path

import pytest
from meliponet.ingest.telemetry import TelemetryError, decode
from mensagem import ESQUEMA, serializar

REPO_ROOT = Path(__file__).resolve().parents[2]
EXEMPLOS = REPO_ROOT / "contracts" / "exemplos"

VALIDAS = sorted(EXEMPLOS.glob("*.json"))
INVALIDAS = sorted((EXEMPLOS / "invalidas").glob("*.json"))


def test_ha_exemplos_para_testar() -> None:
    # Um glob vazio faria todos os testes parametrizados passarem por vacuidade, que
    # e exatamente o modo como esta protecao poderia falhar silenciosamente.
    assert len(VALIDAS) >= 5
    assert len(INVALIDAS) >= 5


@pytest.mark.parametrize("exemplo", VALIDAS, ids=lambda p: p.stem)
def test_exemplo_valido_e_aceito(exemplo: Path) -> None:
    telemetry = decode(exemplo.read_bytes())

    assert telemetry.node_id
    assert telemetry.ts.tzinfo == UTC
    assert telemetry.metrics, "todo exemplo valido carrega ao menos uma metrica"


@pytest.mark.parametrize("exemplo", INVALIDAS, ids=lambda p: p.stem)
def test_exemplo_invalido_e_recusado_com_motivo(exemplo: Path) -> None:
    esperado = exemplo.with_suffix(".motivo").read_text().strip()

    with pytest.raises(TelemetryError) as excinfo:
        decode(exemplo.read_bytes())

    # O motivo precisa ser util para quem for ler `ingest_rejects` meses depois, e para
    # o aluno que so tem a resposta do POST para se guiar.
    assert excinfo.value.reason, f"recusa sem motivo (esperado algo como: {esperado})"


@pytest.mark.parametrize("exemplo", VALIDAS, ids=lambda p: p.stem)
def test_exemplo_sobrevive_a_montagem_em_python(exemplo: Path) -> None:
    """O simulador monta a mesma mensagem que esta no arquivo.

    Nao se exige igualdade byte a byte -- so que os campos e os valores cheguem
    iguais depois de passar por ``mensagem.serializar``. E a garantia de que o
    simulador e os exemplos nao vao divergir sem ninguem notar.
    """
    original = json.loads(exemplo.read_text())

    assert json.loads(serializar(original)) == original


def test_campo_ausente_nao_vira_nulo_nem_zero() -> None:
    montada = json.loads(
        serializar(
            {
                "schema": ESQUEMA,
                "node_id": "A4C1380F",
                "seq": 1,
                "ts": "2027-03-14T12:05:00Z",
                "temp_in_c": 30.12,
                "temp_out_c": None,
            }
        )
    )

    assert "temp_out_c" not in montada


def test_diferencial_termico() -> None:
    telemetry = decode(
        serializar(
            {
                "schema": ESQUEMA,
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
        serializar(
            {
                "schema": ESQUEMA,
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


def test_payload_gigante_e_recusado_sem_parsear() -> None:
    with pytest.raises(TelemetryError, match="excede o limite"):
        decode(b"x" * 5000)
