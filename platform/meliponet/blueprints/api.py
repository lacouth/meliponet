"""A porta por onde o no sensor entrega uma leitura, por HTTP.

Existe para o aluno. O caminho de campo e MQTT (`meliponet/v1/<node_id>/telemetry`), mas
para publicar em MQTT e preciso ter um broker no ar antes de a primeira leitura chegar --
e quem esta escrevendo o firmware do zero precisa ver o ponto aparecer no grafico no
mesmo dia, com o que ja tem na mao. Um POST resolve isso: HTTPClient no ESP32, `curl` na
bancada, e nenhuma peca a mais para instalar.

Os dois caminhos entram no mesmo lugar: `decode()` valida e `store()` grava, os mesmos
que o ingestor MQTT chama. Nada aqui e uma segunda implementacao da ingestao -- se
fosse, os dois caminhos divergiriam e o no que passa a publicar em MQTT (etapa final do
roteiro) veria a plataforma se comportar de outro jeito.
"""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from meliponet.db import session_scope
from meliponet.ingest.store import record_reject, store
from meliponet.ingest.telemetry import TelemetryError, decode

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
        leitura = decode(corpo)
    except TelemetryError as exc:
        # A mensagem recusada e guardada com o motivo, igual ao caminho MQTT: recusa em
        # silencio some, e o aluno fica sem nada para depurar.
        with session_scope() as session:
            record_reject(session, exc.reason, corpo, ORIGEM)
        return jsonify({"erro": exc.reason}), 400

    with session_scope() as session:
        resultado = store(session, leitura)

    if resultado.duplicate:
        # Nao e erro: o no que guardou a leitura durante uma queda de rede vai reenvia-la,
        # e precisa poder apagar a copia local ao receber uma resposta de sucesso.
        return jsonify({"ok": True, "seq": leitura.seq, "repetida": True}), 200

    return jsonify({"ok": True, "seq": leitura.seq, "colmeia": resultado.hive_id}), 201
