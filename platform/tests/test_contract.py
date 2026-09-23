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
from meliponet.ingestao.gravacao import CAMPOS_DE_METRICA
from meliponet.ingestao.telemetria import ErroDeTelemetria, decodificar
from meliponet.modelos import Medicao
from meliponet.servicos.serie import COLUNAS_DE_METRICA
from mensagem import ESQUEMA, serializar

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRATOS = REPO_ROOT / "contracts"
EXEMPLOS = CONTRATOS / "exemplos"

#: Campos do contrato que nao sao metricas de serie. Espelha o frozenset privado de
#: ``meliponet.ingestao.telemetria``; escrito aqui de novo de proposito, para que o
#: teste falhe se alguem mudar um dos dois sem pensar no outro.
NAO_SAO_METRICA = {"schema", "node_id", "seq", "ts", "flags", "gateway_id"}

VALIDAS = sorted(EXEMPLOS.glob("*.json"))
INVALIDAS = sorted((EXEMPLOS / "invalidas").glob("*.json"))


def test_ha_exemplos_para_testar() -> None:
    # Um glob vazio faria todos os testes parametrizados passarem por vacuidade, que
    # e exatamente o modo como esta protecao poderia falhar silenciosamente.
    assert len(VALIDAS) >= 5
    assert len(INVALIDAS) >= 5


@pytest.mark.parametrize("exemplo", VALIDAS, ids=lambda p: p.stem)
def test_exemplo_valido_e_aceito(exemplo: Path) -> None:
    telemetry = decodificar(exemplo.read_bytes())

    assert telemetry.node_id
    assert telemetry.ts.tzinfo == UTC
    assert telemetry.metrics, "todo exemplo valido carrega ao menos uma metrica"


@pytest.mark.parametrize("exemplo", INVALIDAS, ids=lambda p: p.stem)
def test_exemplo_invalido_e_recusado_com_motivo(exemplo: Path) -> None:
    esperado = exemplo.with_suffix(".motivo").read_text().strip()

    with pytest.raises(ErroDeTelemetria) as excinfo:
        decodificar(exemplo.read_bytes())

    # O motivo precisa ser util para quem for ler `ingest_rejects` meses depois, e para
    # o aluno que so tem a resposta do POST para se guiar.
    assert excinfo.value.motivo, f"recusa sem motivo (esperado algo como: {esperado})"


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
    telemetry = decodificar(
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

    assert telemetry.diferencial_termico_c == pytest.approx(-4.68)


def test_diferencial_termico_ausente_sem_sensor_externo() -> None:
    telemetry = decodificar(
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

    assert telemetry.diferencial_termico_c is None
    assert telemetry.flags == ("sht_out_fault",)


def test_payload_gigante_e_recusado_sem_parsear() -> None:
    with pytest.raises(ErroDeTelemetria, match="excede o limite"):
        decodificar(b"x" * 5000)


def test_toda_metrica_do_contrato_e_gravada(exemplos_dir) -> None:
    """O campo que o contrato aceita precisa ter para onde ir no banco.

    Esta e a armadilha do exercicio 03, virada do avesso. Um campo que entra no schema
    e nao entra em ``CAMPOS_DE_METRICA`` e aceito e descartado **em silencio**: a
    mensagem responde 201, o aluno ve sucesso, e a coluna fica NULL para sempre. Sem
    este teste, a divergencia so apareceria semanas depois, olhando um grafico vazio.
    """
    schema = json.loads((CONTRATOS / "telemetry.v1.schema.json").read_text())
    metricas_do_contrato = set(schema["properties"]) - NAO_SAO_METRICA

    faltando = metricas_do_contrato - set(CAMPOS_DE_METRICA)
    assert not faltando, (
        f"o contrato aceita {sorted(faltando)}, mas a gravacao nao grava: "
        "acrescente em meliponet.ingestao.gravacao.CAMPOS_DE_METRICA"
    )


def test_todo_campo_gravado_existe_como_coluna() -> None:
    """As duas listas de campos precisam existir de fato em ``Medicao``.

    ``CAMPOS_DE_METRICA`` vira argumento nomeado do construtor e
    ``COLUNAS_DE_METRICA`` vira ``getattr``. Um nome errado em qualquer uma das duas e
    um erro que so aparece com dado real passando -- aqui aparece na hora.
    """
    colunas = set(Medicao.__table__.columns.keys())

    assert set(CAMPOS_DE_METRICA) <= colunas, sorted(set(CAMPOS_DE_METRICA) - colunas)
    assert set(COLUNAS_DE_METRICA) <= colunas, sorted(set(COLUNAS_DE_METRICA) - colunas)


def test_a_serie_do_grafico_e_um_recorte_do_que_se_grava() -> None:
    """As listas nao sao iguais, e a diferenca e deliberada.

    ``rssi`` e gravado mas nao vira serie: e diagnostico de radio, nao grandeza da
    colmeia. Se um dia as duas listas coincidirem, este teste falha e obriga a decidir
    de novo -- em vez de a diferenca sumir por acidente.
    """
    assert set(COLUNAS_DE_METRICA) < set(CAMPOS_DE_METRICA)
    assert "rssi" in set(CAMPOS_DE_METRICA) - set(COLUNAS_DE_METRICA)
