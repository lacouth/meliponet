"""Configuracao da plataforma, lida do ambiente.

Um unico ponto de leitura de variaveis de ambiente, compartilhado pelo processo web e
pelo ingestor -- que sao processos separados mas precisam concordar sobre o banco.

A regra: o resto da plataforma nao le ``os.environ`` direto; pede uma
:class:`Configuracao` e usa os campos dela.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

#: Fuso de exibicao. Os dados sao sempre gravados em UTC; a conversao acontece so na
#: apresentacao, para que a mudanca de fuso nunca corrompa uma serie ja coletada.
FUSO_DE_EXIBICAO = "America/Fortaleza"

#: Especies-alvo da parceria: nome cientifico e o nome popular pelo qual o
#: meliponicultor as conhece. O cadastro oferece so estas para padronizar a grafia --
#: nomes cientificos digitados a mao divergem e inviabilizam agrupar series por especie.
ESPECIES = [
    ("Melipona scutellaris", "uruçu-nordestina"),
    ("Melipona subnitida", "jandaíra"),
    ("Scaptotrigona depilis", "canudo"),
]

#: So os nomes cientificos, para os campos de escolha dos formularios.
NOMES_CIENTIFICOS = []
for cientifico, _popular in ESPECIES:
    NOMES_CIENTIFICOS.append(cientifico)


def _opcional(nome: str) -> str | None:
    """Le uma variavel de ambiente que pode faltar.

    Variavel definida mas vazia (``MQTT_USERNAME=``) conta como ausente: um texto vazio
    como usuario ou token nunca e o que a pessoa quis dizer.
    """
    valor = os.environ.get(nome)
    if not valor:
        return None
    return valor


# `frozen=True` impede mudar a configuracao depois de montada: web e ingestor leem os
# mesmos valores do comeco ao fim, e uma troca no meio do caminho seria um defeito.
@dataclass(frozen=True)
class Configuracao:
    database_url: str
    secret_key: str
    mqtt_host: str
    mqtt_port: int
    mqtt_username: str | None
    mqtt_password: str | None
    #: Token que a rota HTTP de telemetria exige. Vazio (o padrao) libera a rota, que e
    #: o que permite ao aluno testar com `curl` sem configurar nada.
    token_ingestao: str | None = None

    # `@classmethod` deixa chamar o metodo pela classe, `Configuracao.do_ambiente()`,
    # antes de existir uma configuracao; `cls` e a propria classe `Configuracao`.
    @classmethod
    def do_ambiente(cls) -> Configuracao:
        return cls(
            # SQLite como padrao permite rodar e testar a plataforma sem infraestrutura.
            # Em producao o compose injeta a URL do PostgreSQL/TimescaleDB, e e la que
            # as hypertables e os continuous aggregates entram em acao.
            database_url=os.environ.get("DATABASE_URL", "sqlite:///meliponet.sqlite3"),
            secret_key=os.environ.get("SECRET_KEY", "dev-inseguro-troque-em-producao"),
            mqtt_host=os.environ.get("MQTT_HOST", "localhost"),
            mqtt_port=int(os.environ.get("MQTT_PORT", "1883")),
            mqtt_username=_opcional("MQTT_USERNAME"),
            mqtt_password=_opcional("MQTT_PASSWORD"),
            token_ingestao=_opcional("TOKEN_INGESTAO"),
        )
