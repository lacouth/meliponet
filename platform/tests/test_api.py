"""Testes da rota HTTP de telemetria -- a porta que o no do aluno usa.

Cada teste aqui corresponde a uma coisa que o aluno vai ver na bancada: o 201 que
confirma a primeira leitura, o 400 que explica o que esta errado na mensagem, e o 200 do
reenvio, que o firmware precisa poder distinguir de uma falha para apagar a copia local.
"""

from __future__ import annotations

import json

from meliponet.banco import abrir_sessao
from meliponet.configuracao import Configuracao
from meliponet.modelos import Medicao, Recusa
from mensagem import ESQUEMA, serializar
from sqlalchemy import select

ROTA = "/api/v1/telemetria"


def leitura(seq: int = 1, node_id: str = "A4C13800", **extra) -> str:
    return serializar(
        {
            "schema": ESQUEMA,
            "node_id": node_id,
            "seq": seq,
            "ts": "2027-03-14T12:05:00Z",
            "temp_in_c": 30.12,
            "weight_kg": 12.483,
            **extra,
        }
    )


def postar(client, corpo: str, **kwargs):
    return client.post(ROTA, data=corpo, content_type="application/json", **kwargs)


def test_leitura_valida_e_gravada(client, cenario) -> None:
    resposta = postar(client, leitura())

    assert resposta.status_code == 201
    corpo = resposta.get_json()
    assert corpo["ok"] is True
    assert corpo["colmeia"] == cenario.colmeia_id

    with abrir_sessao() as session:
        row = session.scalar(select(Medicao))
        assert row.node_id == "A4C13800"
        assert row.seq == 1


def test_reenvio_responde_sucesso_e_nao_duplica(client, cenario) -> None:
    """O no que guardou a leitura durante uma queda vai reenvia-la.

    Se o reenvio respondesse erro, o firmware do aluno guardaria a copia local para
    sempre -- e a memoria do no acabaria enchendo por causa de uma leitura que a
    plataforma ja tinha.
    """
    assert postar(client, leitura(7)).status_code == 201
    resposta = postar(client, leitura(7, flags=["spooled"]))

    assert resposta.status_code == 200
    assert resposta.get_json()["repetida"] is True

    with abrir_sessao() as session:
        assert len(session.scalars(select(Medicao)).all()) == 1


def test_mensagem_invalida_responde_o_motivo_e_fica_registrada(client, cenario) -> None:
    resposta = postar(client, json.dumps({"schema": ESQUEMA, "node_id": "A4C13800"}))

    assert resposta.status_code == 400
    assert resposta.get_json()["erro"]

    with abrir_sessao() as session:
        recusa = session.scalar(select(Recusa))
        assert recusa is not None
        assert recusa.reason
        assert recusa.topic == "http:/api/v1/telemetria"


def test_json_malformado_nao_derruba_a_rota(client, cenario) -> None:
    resposta = postar(client, '{"schema": "meliponet.telemetry.v1", "seq": 1,')

    assert resposta.status_code == 400
    assert "malformado" in resposta.get_json()["erro"]


def test_token_e_exigido_quando_configurado(db, cenario) -> None:
    from meliponet import criar_app

    app = criar_app(
        Configuracao(
            database_url=str(db.url),
            secret_key="teste",
            mqtt_host="localhost",
            mqtt_port=1883,
            mqtt_username=None,
            mqtt_password=None,
            token_ingestao="segredo-do-meliponario",
        )
    )
    app.config["TESTING"] = True
    client = app.test_client()

    assert postar(client, leitura()).status_code == 401
    assert postar(client, leitura(), headers={"Authorization": "Bearer errado"}).status_code == 401

    aceita = postar(
        client, leitura(), headers={"Authorization": "Bearer segredo-do-meliponario"}
    )
    assert aceita.status_code == 201
