"""Gera telemetria sintetica conforme o contrato e a entrega a plataforma.

O simulador desacopla o desenvolvimento da plataforma da entrega do hardware: ele emite
a mesma mensagem que o no sensor emite -- montada pelo mesmo ``contracts/mensagem.py``
--, de modo que tudo rio abaixo (validacao, persistencia, graficos, alertas) e
exercitado pelo caminho real, antes de existir placa.

Tres transportes:

``--transporte mqtt`` (padrao)
    Publica no broker, como um no de campo. E o caminho completo.

``--transporte http``
    Faz o mesmo POST que o no do aluno faz (``/api/v1/telemetria``), contra um servidor
    ja no ar. Serve para exercitar a rota ponta a ponta -- e para ter, ao lado do
    firmware que nao envia, um remetente que sabidamente funciona.

``--transporte direto``
    Chama o mesmo pipeline de ingestao sem passar por rede nenhuma. Serve para testar a
    plataforma numa maquina sem Mosquitto e sem servidor no ar. O codigo exercitado e o
    mesmo, menos o transporte -- o que ele **nao** testa e a reentrega do broker e o
    comportamento sob reconexao.

E injeta falhas de proposito (``--falhas``), porque a plataforma precisa ser
desenvolvida contra dados imperfeitos: lacunas, deriva de sensor, outliers e sensor
mudo sao o insumo das rotinas de qualidade e curadoria do Edital 17.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
for path in (REPO_ROOT / "platform", REPO_ROOT / "contracts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from mensagem import ESQUEMA, serializar

from simulator.model import HiveSimulator

LOGGER = logging.getLogger("simulator")

#: Meliponarios e especies da parceria, nos municipios previstos nas propostas.
APIARIES = [
    ("Meliponário Mata do Buraquinho", "João Pessoa", -7.1408, -34.8556),
    ("Meliponário Campina", "Campina Grande", -7.2306, -35.8811),
]

SPECIES = [
    "Melipona scutellaris",
    "Melipona subnitida",
    "Scaptotrigona depilis",
]

FAULTS = ("lacunas", "deriva", "outliers", "sensor-mudo", "bateria")


def build_hives(count: int) -> list[HiveSimulator]:
    hives = []
    for index in range(count):
        # node_id no formato do contrato: 8 digitos hexadecimais maiusculos.
        node_id = f"{0xA4C13800 + index:08X}"
        hives.append(
            HiveSimulator(
                node_id=node_id,
                name=f"Colmeia {index + 1:02d}",
                species=SPECIES[index % len(SPECIES)],
                weight_kg=10.0 + index * 1.7,
            )
        )
    return hives


def make_message(hive: HiveSimulator, when: datetime, faults: set[str]) -> dict | None:
    """Monta uma mensagem. Devolve ``None`` quando a falha injetada e uma lacuna."""
    rng = hive.rng
    hive.seq += 1

    # Lacuna: a mensagem simplesmente nao sai. A `seq` avanca mesmo assim, que e o que
    # permite a plataforma detectar a perda contando saltos na sequencia.
    if "lacunas" in faults and rng.random() < 0.04:
        return None

    outside = hive.outside_temp_c(when)
    inside = hive.inside_temp_c(when, outside)

    # Deriva de calibracao: o sensor vai se afastando lentamente do valor real,
    # exatamente como um SHT30 coberto de cerume e propolis.
    if "deriva" in faults:
        inside += hive.seq * 0.0008

    # Outlier isolado: leitura absurda porem dentro da faixa fisica do sensor, que a
    # validacao sintatica nao pega e a curadoria precisa marcar.
    if "outliers" in faults and rng.random() < 0.01:
        inside += rng.choice([-1, 1]) * rng.uniform(8, 15)

    message = {
        "schema": ESQUEMA,
        "node_id": hive.node_id,
        "seq": hive.seq,
        "ts": when.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "temp_in_c": inside,
        "temp_out_c": outside,
        "rh_in_pct": hive.inside_rh_pct(when),
        "rh_out_pct": hive.outside_rh_pct(when),
        "weight_kg": hive.step_weight_kg(when),
        "vbat_v": hive.step_battery_v(when),
        "rssi": int(rng.gauss(-62, 6)),
    }

    flags: list[str] = []

    # Sensor externo mudo: os campos externos somem e a flag explica. Nao viram zero --
    # a plataforma precisa distinguir "sem sensor" de "leu zero".
    if "sensor-mudo" in faults and rng.random() < 0.03:
        message.pop("temp_out_c")
        message.pop("rh_out_pct")
        flags.append("sht_out_fault")

    if "bateria" in faults and message["vbat_v"] < 3.5:
        flags.append("low_batt")

    if flags:
        message["flags"] = flags
    return message


def resume_state(hives: list[HiveSimulator]) -> None:
    """Retoma ``seq``, peso e bateria de onde a ultima execucao parou.

    Sem isso, um simulador reiniciado recomecaria a sequencia em 1 e a plataforma
    descartaria tudo como reenvio de spool -- corretamente, pela restricao
    ``UNIQUE (node_id, seq)``, mas deixando o simulador aparentemente mudo.

    E o mesmo comportamento do no real, que persiste a ``seq`` em NVS justamente para
    sobreviver a um reset sem colidir com o que ja mandou. Retomar tambem peso e
    bateria evita um degrau artificial na serie a cada reinicio.
    """
    from meliponet.db import session_scope
    from meliponet.models import Measurement
    from sqlalchemy import func, select

    with session_scope() as session:
        for hive in hives:
            last_seq = session.scalar(
                select(func.max(Measurement.seq)).where(Measurement.node_id == hive.node_id)
            )
            if last_seq is None:
                continue
            hive.seq = last_seq

            last = session.scalar(
                select(Measurement)
                .where(Measurement.node_id == hive.node_id)
                .order_by(Measurement.time.desc())
                .limit(1)
            )
            if last is not None:
                if last.weight_kg is not None:
                    hive.weight_kg = last.weight_kg
                if last.vbat_v is not None:
                    hive.battery_v = last.vbat_v
            LOGGER.info("nó %s retomado na seq %d", hive.node_id, hive.seq)


def seed_database(hives: list[HiveSimulator], organization: str, history_hours: int) -> None:
    """Cadastra organizacao, meliponarios, colmeias, nos e vinculos.

    O vinculo e aberto com ``installed_at`` recuado antes do inicio do historico. Sem
    isso, as leituras sinteticas anteriores a instalacao ficariam sem colmeia -- que e
    o comportamento correto do modelo, ja que a colmeia de uma leitura e resolvida pelo
    instante da medicao, mas nao e o que se quer de um seed de demonstracao.
    """
    from meliponet.db import session_scope
    from meliponet.models import Apiary, Hive, Node, NodeAssignment, Organization
    from sqlalchemy import select

    installed_at = datetime.now(UTC) - timedelta(hours=history_hours + 1)

    with session_scope() as session:
        org = session.scalar(select(Organization).where(Organization.name == organization))
        if org is None:
            org = Organization(name=organization)
            session.add(org)
            session.flush()

        apiaries = []
        for name, municipality, lat, lon in APIARIES:
            # O nome do meliponario so e unico dentro de uma organizacao: duas
            # organizacoes podem ter um "Meliponario Campina" cada uma. Sem o filtro
            # por organizacao, um seed pedido para a organizacao B encontraria o
            # meliponario da organizacao A e penduraria as colmeias dela la.
            apiary = session.scalar(
                select(Apiary).where(
                    Apiary.name == name, Apiary.organization_id == org.id
                )
            )
            if apiary is None:
                apiary = Apiary(
                    organization_id=org.id,
                    name=name,
                    municipality=municipality,
                    latitude=lat,
                    longitude=lon,
                )
                session.add(apiary)
                session.flush()
            apiaries.append(apiary)

        for index, sim in enumerate(hives):
            node = session.scalar(select(Node).where(Node.node_id == sim.node_id))
            if node is not None and node.current_assignment is not None:
                continue

            apiary = apiaries[index % len(apiaries)]
            hive = session.scalar(
                select(Hive).where(Hive.name == sim.name, Hive.apiary_id == apiary.id)
            )
            if hive is None:
                hive = Hive(
                    apiary_id=apiary.id,
                    name=sim.name,
                    species=sim.species,
                    installed_at=installed_at,
                )
                session.add(hive)
                session.flush()

            if node is None:
                node = Node(node_id=sim.node_id, label=f"MelipoSense {sim.node_id}")
                session.add(node)
                session.flush()
            node.organization_id = org.id

            session.add(
                NodeAssignment(
                    node_id=node.id,
                    hive_id=hive.id,
                    installed_at=installed_at,
                    sensor_placement=(
                        "SHT30 interno na parede lateral, 2 cm acima do invólucro de "
                        "cerume; SHT30 externo à sombra sob a tampa; célula de carga "
                        "sob o ninho."
                    ),
                    protocol_notes="Instalação sintética gerada pelo simulador.",
                )
            )

        LOGGER.info(
            "cadastrados %d meliponários e %d colmeias em %s",
            len(apiaries),
            len(hives),
            organization,
        )


class DirectPublisher:
    """Entrega a mensagem ao mesmo pipeline de ingestao, sem passar pelo broker."""

    def __init__(self) -> None:
        from meliponet.ingest.__main__ import handle_message

        self._handle = handle_message

    def publish(self, node_id: str, payload: str) -> None:
        self._handle(payload.encode("utf-8"), f"meliponet/v1/{node_id}/telemetry")

    def close(self) -> None:
        pass


class HttpPublisher:
    """Faz o mesmo POST que o no do aluno faz, contra um servidor ja no ar."""

    def __init__(self, url: str, token: str | None) -> None:
        self._url = url
        self._token = token
        LOGGER.info("publicando em %s", url)

    def publish(self, node_id: str, payload: str) -> None:
        import urllib.error
        import urllib.request

        pedido = urllib.request.Request(
            self._url,
            data=payload.encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        if self._token:
            pedido.add_header("Authorization", f"Bearer {self._token}")
        try:
            with urllib.request.urlopen(pedido, timeout=10) as resposta:
                resposta.read()
        except urllib.error.HTTPError as erro:
            # Recusa da plataforma nao e motivo para parar: o simulador injeta falhas de
            # proposito, e ver o motivo passar no log e parte do que ele serve.
            LOGGER.warning("no %s recusado (%s): %s", node_id, erro.code, erro.read().decode())

    def close(self) -> None:
        pass


class MqttPublisher:
    """Publica no broker, como um no de verdade."""

    def __init__(self, host: str, port: int, username: str | None, password: str | None) -> None:
        import paho.mqtt.client as mqtt

        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        if username:
            self._client.username_pw_set(username, password)
        self._client.connect(host, port, keepalive=60)
        self._client.loop_start()
        LOGGER.info("publicando em %s:%s", host, port)

    def publish(self, node_id: str, payload: str) -> None:
        # QoS 1: o no de campo nao pode perder uma leitura porque o broker estava
        # ocupado, e o simulador precisa exercitar o mesmo nivel de garantia.
        self._client.publish(f"meliponet/v1/{node_id}/telemetry", payload, qos=1)

    def close(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()


def run_realtime(
    hives: list[HiveSimulator],
    faults: set[str],
    publisher: DirectPublisher | MqttPublisher,
    period_s: float,
    emitted: int = 0,
    rounds: int | None = None,
) -> int:
    """Emite indefinidamente, uma rodada de amostras por vez.

    ``rounds`` limita o numero de rodadas; e o que permite um teste rodar a funcao sem
    ficar preso no laco. Em uso normal fica ``None``, e so o Ctrl+C interrompe.
    """
    LOGGER.info("tempo real: uma amostra a cada %.1f s (Ctrl+C para parar)", period_s)
    completed = 0
    try:
        while rounds is None or completed < rounds:
            # O instante vem do relogio a cada rodada. Somar `--intervalo` aqui faria o
            # tempo simulado correr mais rapido que o real (5 min a cada 3 s, nos
            # padroes) e as leituras cairiam no futuro, onde o painel -- que so olha
            # ate agora -- nao as mostra. O `--intervalo` governa so o historico.
            when = datetime.now(UTC)
            for hive in hives:
                message = make_message(hive, when, faults)
                if message is None:
                    continue
                publisher.publish(hive.node_id, serializar(message))
                emitted += 1
            LOGGER.info("%d medições emitidas", emitted)
            completed += 1
            time.sleep(period_s)
    except KeyboardInterrupt:
        LOGGER.info("interrompido; %d medições emitidas", emitted)
    return emitted


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="simulator", description=__doc__)
    parser.add_argument("--colmeias", type=int, default=4, help="quantas colmeias simular")
    parser.add_argument(
        "--transporte", choices=("mqtt", "http", "direto"), default="mqtt",
        help="mqtt publica no broker; http faz POST na rota de telemetria; "
             "direto chama a ingestão sem rede",
    )
    parser.add_argument(
        "--url", default="http://127.0.0.1:5000/api/v1/telemetria",
        help="endereço da rota de telemetria, usado por --transporte http",
    )
    parser.add_argument(
        "--historico", type=int, default=48,
        help="horas de histórico a gerar antes de começar o tempo real (0 desliga)",
    )
    parser.add_argument(
        "--intervalo", type=int, default=300,
        help="segundos entre amostras no histórico (padrão: 5 min, como o nó real); "
             "no tempo real quem espaça as amostras é --periodo",
    )
    parser.add_argument(
        "--periodo", type=float, default=3.0,
        help="segundos reais entre uma amostra e a próxima no modo tempo real",
    )
    parser.add_argument(
        "--falhas", default="lacunas,sensor-mudo,bateria",
        help=f"falhas a injetar, separadas por vírgula. Disponíveis: {', '.join(FAULTS)}",
    )
    parser.add_argument(
        "--tempo-real", action="store_true",
        help="continua emitindo após o histórico",
    )
    parser.add_argument(
        "--organizacao", default="Meliponicultores da Paraíba",
        help="organização dona dos meliponários simulados",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    # A telemetria de cada leitura polui a saida do simulador; o que importa aqui e o
    # progresso da geracao.
    logging.getLogger("meliponet.ingest").setLevel(logging.WARNING)

    args = parse_args(argv)
    faults = {f.strip() for f in args.falhas.split(",") if f.strip()}
    unknown = faults - set(FAULTS)
    if unknown:
        print(f"falhas desconhecidas: {', '.join(sorted(unknown))}", file=sys.stderr)
        return 2

    from meliponet.config import Config
    from meliponet.db import create_all, init_engine

    config = Config.from_env()
    hives = build_hives(args.colmeias)

    if args.transporte == "direto":
        engine = init_engine(config.database_url)
        create_all(engine)
        seed_database(hives, args.organizacao, args.historico)
        resume_state(hives)
        publisher: DirectPublisher | HttpPublisher | MqttPublisher = DirectPublisher()
    elif args.transporte == "http":
        # O cadastro precisa existir para a telemetria pousar numa colmeia; a gravacao
        # da telemetria em si e do servidor que atende o POST.
        engine = init_engine(config.database_url)
        create_all(engine)
        seed_database(hives, args.organizacao, args.historico)
        resume_state(hives)
        publisher = HttpPublisher(args.url, config.token_ingestao)
    else:
        # No modo MQTT o simulador nao toca no banco: quem grava e o ingestor, como em
        # producao. Mas o cadastro precisa existir para a telemetria pousar numa
        # colmeia, entao ele e feito uma vez aqui.
        engine = init_engine(config.database_url)
        create_all(engine)
        seed_database(hives, args.organizacao, args.historico)
        resume_state(hives)
        publisher = MqttPublisher(
            config.mqtt_host, config.mqtt_port, config.mqtt_username, config.mqtt_password
        )

    step = timedelta(seconds=args.intervalo)
    emitted = skipped = 0

    try:
        if args.historico:
            start = datetime.now(UTC) - timedelta(hours=args.historico)
            when = start
            end = datetime.now(UTC)
            LOGGER.info(
                "gerando %d h de histórico para %d colmeias...", args.historico, len(hives)
            )
            while when < end:
                for hive in hives:
                    message = make_message(hive, when, faults)
                    if message is None:
                        skipped += 1
                        continue
                    publisher.publish(hive.node_id, serializar(message))
                    emitted += 1
                when += step
            LOGGER.info("histórico pronto: %d medições, %d lacunas injetadas", emitted, skipped)

        if args.tempo_real:
            emitted = run_realtime(hives, faults, publisher, args.periodo, emitted)
    except KeyboardInterrupt:
        LOGGER.info("interrompido; %d medições emitidas", emitted)
    finally:
        publisher.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
