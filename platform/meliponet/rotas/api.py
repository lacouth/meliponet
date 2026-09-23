"""A porta por onde o no sensor entrega uma leitura, por HTTP.

Existe para quem esta escrevendo o firmware: um POST nao exige broker no ar, entao o
primeiro ponto aparece no grafico no mesmo dia. `decodificar()` valida e `gravar()`
grava -- as mesmas funcoes do ingestor MQTT, nunca uma segunda implementacao.

E a unica rota que abre a sessao na mao: ela grava a recusa e responde 400, e a sessao
da requisicao desfaria esse registro. O porque completo esta em
``docs/guia/03-a-plataforma.md``.
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
