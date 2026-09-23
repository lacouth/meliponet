"""Consumidor MQTT: o processo que leva a telemetria do broker ao banco.

Roda separado do Flask de proposito. O servidor web pode reiniciar, escalar ou cair
sem que se perca telemetria, porque quem mantem a sessao MQTT persistente e este
processo -- e as mensagens QoS 1 publicadas durante um reinicio ficam na fila do
broker em vez de sumirem. Um deploy da plataforma nao pode abrir uma lacuna nas series,
ja que lacuna e justamente o que o Edital 17 se propoe a medir e minimizar.
"""

from __future__ import annotations

import logging
import signal
import sys
from types import FrameType

import paho.mqtt.client as mqtt

from meliponet.banco import abrir_sessao, criar_tabelas, iniciar_banco
from meliponet.configuracao import Configuracao
from meliponet.ingestao import gravacao
from meliponet.ingestao.telemetria import ErroDeTelemetria, decodificar

LOGGER = logging.getLogger("meliponet.ingestao")

#: Assina toda a v1: os nos publicam direto por WiFi na Fase 3 e, na Fase 5, o gateway
#: LoRa publica no mesmo topico. Do broker para dentro, nada muda.
TOPICO_DE_TELEMETRIA = "meliponet/v1/+/telemetry"

#: Identidade estavel da sessao. Com `clean_session=False`, e o que permite ao broker
#: guardar as mensagens QoS 1 enquanto este processo esta fora do ar.
ID_DO_CLIENTE = "meliponet-ingest"


def tratar_mensagem(payload: bytes, topico: str) -> None:
    """Valida e grava uma mensagem. Recusas sao registradas, nunca silenciadas."""
    try:
        leitura = decodificar(payload)
    except ErroDeTelemetria as exc:
        LOGGER.warning("mensagem recusada em %s: %s", topico, exc.motivo)
        with abrir_sessao() as session:
            gravacao.registrar_recusa(session, exc.motivo, payload, topico)
        return

    with abrir_sessao() as session:
        resultado = gravacao.gravar(session, leitura)

    if resultado.duplicate:
        LOGGER.debug("reenvio ignorado: no %s seq %s", leitura.node_id, leitura.seq)
    else:
        LOGGER.info("gravado: no %s seq %s em %s", leitura.node_id, leitura.seq, leitura.ts)


def montar_cliente(configuracao: Configuracao) -> mqtt.Client:
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=ID_DO_CLIENTE,
        clean_session=False,
    )
    if configuracao.mqtt_username:
        client.username_pw_set(configuracao.mqtt_username, configuracao.mqtt_password)

    def on_connect(client: mqtt.Client, _userdata, _flags, reason_code, _properties=None):
        if reason_code != 0:
            LOGGER.error("falha ao conectar no broker: %s", reason_code)
            return
        LOGGER.info("conectado ao broker; assinando %s", TOPICO_DE_TELEMETRIA)
        # A assinatura e refeita a cada conexao, e nao so na primeira: apos uma queda
        # de rede o broker pode ter perdido a sessao, e sem reassinar o ingestor
        # ficaria conectado porem surdo.
        client.subscribe(TOPICO_DE_TELEMETRIA, qos=1)

    def on_message(_client: mqtt.Client, _userdata, message: mqtt.MQTTMessage):
        try:
            tratar_mensagem(message.payload, message.topic)
        except Exception:
            # Uma falha ao processar uma mensagem nao pode derrubar o consumidor e
            # parar a ingestao de todas as outras colmeias.
            LOGGER.exception("erro inesperado processando mensagem de %s", message.topic)

    client.on_connect = on_connect
    client.on_message = on_message
    return client


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    configuracao = Configuracao.do_ambiente()

    engine = iniciar_banco(configuracao.database_url)
    criar_tabelas(engine)

    client = montar_cliente(configuracao)

    def shutdown(_signum: int, _frame: FrameType | None) -> None:
        LOGGER.info("encerrando")
        client.disconnect()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    LOGGER.info("conectando em %s:%s", configuracao.mqtt_host, configuracao.mqtt_port)
    client.connect(configuracao.mqtt_host, configuracao.mqtt_port, keepalive=60)
    client.loop_forever(retry_first_connection=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
