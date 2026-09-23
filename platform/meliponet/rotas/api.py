"""A porta por onde o no sensor entrega uma leitura, por HTTP.

Existe para o aluno. O caminho de campo e MQTT (`meliponet/v1/<node_id>/telemetry`), mas
para publicar em MQTT e preciso ter um broker no ar antes de a primeira leitura chegar --
e quem esta escrevendo o firmware do zero precisa ver o ponto aparecer no grafico no
mesmo dia, com o que ja tem na mao. Um POST resolve isso: HTTPClient no ESP32, `curl` na
bancada, e nenhuma peca a mais para instalar.

Os dois caminhos entram no mesmo lugar: `decodificar()` valida e `gravar()` grava, os mesmos
que o ingestor MQTT chama. Nada aqui e uma segunda implementacao da ingestao -- se
fosse, os dois caminhos divergiriam e o no que passa a publicar em MQTT (etapa final do
roteiro) veria a plataforma se comportar de outro jeito.

Esta e a unica rota que abre a sessao na mao, com `abrir_sessao()`, em vez de usar a
sessao da requisicao: ela **grava a recusa e responde 400**, e a sessao da requisicao
desfaz o que a resposta de erro tocou. E o comportamento certo para as telas e o errado
aqui -- sem a recusa gravada, o aluno fica sem nada para depurar.
"""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from meliponet.banco import abrir_sessao
from meliponet.ingestao.gravacao import gravar, registrar_recusa
from meliponet.ingestao.telemetria import ErroDeTelemetria, decodificar

bp = Blueprint("api", __name__, url_prefix="/api/v1")

#: Origem registrada nas recusas, no lugar do topico MQTT. Quem for ler
#: `ingest_rejects` meses depois precisa saber por qual porta a mensagem entrou.
ORIGEM = "http:/api/v1/telemetria"


def _token_confere() -> bool:
    """O token e opcional de proposito.

    Sem `TOKEN_INGESTAO` no ambiente, a rota aceita qualquer POST -- e o padrao em
    desenvolvimento, e e o que permite ao aluno testar com `curl` sem configurar nada.
    Em campo a variavel e definida, e ai o no precisa apresenta-la.
    """
    esperado = current_app.config["MELIPONET"].token_ingestao
    if not esperado:
        return True
    cabecalho = request.headers.get("Authorization", "")
    return cabecalho == f"Bearer {esperado}"


@bp.post("/telemetria")
def telemetria():
    if not _token_confere():
        return jsonify({"erro": "token de ingestao ausente ou invalido"}), 401

    corpo = request.get_data()

    try:
        leitura = decodificar(corpo)
    except ErroDeTelemetria as exc:
        # A mensagem recusada e guardada com o motivo, igual ao caminho MQTT: recusa em
        # silencio some, e o aluno fica sem nada para depurar.
        with abrir_sessao() as session:
            registrar_recusa(session, exc.motivo, corpo, ORIGEM)
        return jsonify({"erro": exc.motivo}), 400

    with abrir_sessao() as session:
        resultado = gravar(session, leitura)

    if resultado.duplicate:
        # Nao e erro: o no que guardou a leitura durante uma queda de rede vai reenvia-la,
        # e precisa poder apagar a copia local ao receber uma resposta de sucesso.
        return jsonify({"ok": True, "seq": leitura.seq, "repetida": True}), 200

    return jsonify({"ok": True, "seq": leitura.seq, "colmeia": resultado.hive_id}), 201
