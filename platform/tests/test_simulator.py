"""Testes do simulador.

Cobrem as duas armadilhas que fizeram o painel parecer parado: o meliponario
encontrado na organizacao errada e a serie em tempo real correndo para o futuro.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from simulator.__main__ import build_hives, run_realtime


class FakePublisher:
    """Guarda as mensagens em memoria, no lugar do broker ou da ingestao."""

    def __init__(self) -> None:
        self.messages: list[dict] = []

    def publish(self, node_id: str, payload: str) -> None:
        self.messages.append(json.loads(payload))

    def close(self) -> None:
        pass


def test_tempo_real_nao_gera_leitura_no_futuro():
    """O ``ts`` de cada rodada vem do relogio, e nao de um contador que corre solto.

    Com o padrao antigo -- ``when += intervalo`` a cada rodada -- o tempo simulado
    andava 5 min a cada 3 s reais, e as leituras caiam dias a frente. O painel, que so
    olha ate agora, mostrava a colmeia parada mesmo com o simulador emitindo.
    """
    publisher = FakePublisher()
    hives = build_hives(2)

    run_realtime(hives, set(), publisher, period_s=0.0, rounds=5)

    limite = datetime.now(UTC) + timedelta(seconds=1)
    for message in publisher.messages:
        ts = datetime.strptime(message["ts"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
        assert ts <= limite, f"leitura no futuro: {message['ts']}"


def test_seed_encontra_o_meliponario_da_propria_organizacao(db):
    """Duas organizacoes podem ter meliponarios de mesmo nome, e cada uma fica com o seu.

    O seed procurava o meliponario so pelo nome: um simulador apontado para a
    organizacao B encontrava o meliponario homonimo da A e pendurava as colmeias novas
    la, onde ninguem da B as veria.
    """
    from meliponet.db import session_scope
    from meliponet.models import Apiary, Organization
    from sqlalchemy import select

    from simulator.__main__ import APIARIES, seed_database
    from simulator.model import HiveSimulator

    seed_database([HiveSimulator(node_id="A4C13900", name="Colmeia 01", species="M")], "Org A", 1)
    seed_database([HiveSimulator(node_id="A4C13901", name="Colmeia 01", species="M")], "Org B", 1)

    nome = APIARIES[0][0]
    with session_scope() as session:
        apiaries = list(session.scalars(select(Apiary).where(Apiary.name == nome)))
        assert len(apiaries) == 2, "cada organizacao precisa do seu proprio meliponario"

        donos = {
            session.get(Organization, apiary.organization_id).name for apiary in apiaries
        }
        assert donos == {"Org A", "Org B"}
