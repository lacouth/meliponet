"""Configuracao da plataforma, lida do ambiente.

Um unico ponto de leitura de variaveis de ambiente, compartilhado pelo processo web e
pelo ingestor -- que sao processos separados mas precisam concordar sobre o banco.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

#: Fuso de exibicao. Os dados sao sempre gravados em UTC; a conversao acontece so na
#: apresentacao, para que a mudanca de fuso nunca corrompa uma serie ja coletada.
DISPLAY_TIMEZONE = "America/Fortaleza"


@dataclass(frozen=True, slots=True)
class Config:
    database_url: str
    secret_key: str
    mqtt_host: str
    mqtt_port: int
    mqtt_username: str | None
    mqtt_password: str | None

    @classmethod
    def from_env(cls) -> Config:
        return cls(
            # SQLite como padrao permite rodar e testar a plataforma sem infraestrutura.
            # Em producao o compose injeta a URL do PostgreSQL/TimescaleDB, e e la que
            # as hypertables e os continuous aggregates entram em acao.
            database_url=os.environ.get("DATABASE_URL", "sqlite:///meliponet.sqlite3"),
            secret_key=os.environ.get("SECRET_KEY", "dev-inseguro-troque-em-producao"),
            mqtt_host=os.environ.get("MQTT_HOST", "localhost"),
            mqtt_port=int(os.environ.get("MQTT_PORT", "1883")),
            mqtt_username=os.environ.get("MQTT_USERNAME") or None,
            mqtt_password=os.environ.get("MQTT_PASSWORD") or None,
        )
