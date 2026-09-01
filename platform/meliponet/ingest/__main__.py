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

from meliponet.config import Config
from meliponet.db import create_all, init_engine, session_scope
from meliponet.ingest import store as store_module
from meliponet.ingest.telemetry import TelemetryError, decode

LOGGER = logging.getLogger("meliponet.ingest")

#: Assina toda a v1: os nos publicam direto por WiFi na Fase 3 e, na Fase 5, o gateway
#: LoRa publica no mesmo topico. Do broker para dentro, nada muda.
TELEMETRY_TOPIC = "meliponet/v1/+/telemetry"

#: Identidade estavel da sessao. Com `clean_session=False`, e o que permite ao broker
#: guardar as mensagens QoS 1 enquanto este processo esta fora do ar.
CLIENT_ID = "meliponet-ingest"


def handle_message(payload: bytes, topic: str) -> None:
    """Valida e grava uma mensagem. Recusas sao registradas, nunca silenciadas."""
    try:
        telemetry = decode(payload)
    except TelemetryError as exc:
        LOGGER.warning("mensagem recusada em %s: %s", topic, exc.reason)
        with session_scope() as session:
            store_module.record_reject(session, exc.reason, payload, topic)
        return

    with session_scope() as session:
        result = store_module.store(session, telemetry)

    if result.duplicate:
        LOGGER.debug("reenvio ignorado: no %s seq %s", telemetry.node_id, telemetry.seq)
    else:
        LOGGER.info(
            "gravado: no %s seq %s em %s", telemetry.node_id, telemetry.seq, telemetry.ts
        )


def build_client(config: Config) -> mqtt.Client:
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=CLIENT_ID,
        clean_session=False,
    )
    if config.mqtt_username:
        client.username_pw_set(config.mqtt_username, config.mqtt_password)

    def on_connect(client: mqtt.Client, _userdata, _flags, reason_code, _properties=None):
        if reason_code != 0:
            LOGGER.error("falha ao conectar no broker: %s", reason_code)
            return
        LOGGER.info("conectado ao broker; assinando %s", TELEMETRY_TOPIC)
        # A assinatura e refeita a cada conexao, e nao so na primeira: apos uma queda
        # de rede o broker pode ter perdido a sessao, e sem reassinar o ingestor
        # ficaria conectado porem surdo.
        client.subscribe(TELEMETRY_TOPIC, qos=1)

    def on_message(_client: mqtt.Client, _userdata, message: mqtt.MQTTMessage):
        try:
            handle_message(message.payload, message.topic)
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
    config = Config.from_env()

    engine = init_engine(config.database_url)
    create_all(engine)

    client = build_client(config)

    def shutdown(_signum: int, _frame: FrameType | None) -> None:
        LOGGER.info("encerrando")
        client.disconnect()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    LOGGER.info("conectando em %s:%s", config.mqtt_host, config.mqtt_port)
    client.connect(config.mqtt_host, config.mqtt_port, keepalive=60)
    client.loop_forever(retry_first_connection=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
