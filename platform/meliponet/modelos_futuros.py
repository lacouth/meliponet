"""Tabelas criadas desde ja para a Fase 4. **Nenhum codigo as usa ainda.**

Existem no banco para que a Fase 4 (calibracao e alertas) nao exija migracao quando
chegar. Moram fora de ``modelos.py`` para que quem esta aprendendo o modelo leia so o
que o sistema usa hoje.

Quem precisa de todas as tabelas -- ``banco.criar_tabelas`` e o Alembic -- importa este
arquivo junto com ``modelos.py``.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from meliponet.modelos import Base, Colmeia, DataHoraUtc, No, agora_utc


class Calibracao(Base):
    """Calibracao de um sensor de um no, com o historico das aplicacoes.

    Fica no banco, e nao so na NVS do no, porque a deriva ao longo do tempo e um dos
    resultados que o Edital 17 se propoe a quantificar -- e para isso e preciso saber
    quando cada tara foi refeita.
    """

    __tablename__ = "calibrations"

    id: Mapped[int] = mapped_column(primary_key=True)
    node_id: Mapped[int] = mapped_column(ForeignKey("nodes.id"), nullable=False)
    #: "hx711", "sht_in" ou "sht_out".
    sensor: Mapped[str] = mapped_column(String(20), nullable=False)
    offset: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    scale: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    applied_at: Mapped[datetime] = mapped_column(DataHoraUtc, nullable=False, default=agora_utc)
    notes: Mapped[str | None] = mapped_column(Text)

    node: Mapped[No] = relationship()


class RegraDeAlerta(Base):
    """Regra de deteccao de anomalia."""

    __tablename__ = "alert_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    #: Regra especifica de uma colmeia; nula quando vale para uma especie inteira.
    hive_id: Mapped[int | None] = mapped_column(ForeignKey("hives.id"))
    species: Mapped[str | None] = mapped_column(String(120))
    metric: Mapped[str] = mapped_column(String(40), nullable=False)
    #: "gt", "lt" ou "drop" (queda abrupta em relacao a janela anterior).
    comparison: Mapped[str] = mapped_column(String(10), nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    #: Quantas leituras consecutivas precisam violar antes de abrir o alerta. Evita
    #: que um outlier isolado dispare notificacao para o produtor.
    sustained_samples: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    description: Mapped[str | None] = mapped_column(Text)


class Alerta(Base):
    """Ocorrencia de uma regra: quando abriu, quando fechou, com que valor."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    hive_id: Mapped[int] = mapped_column(ForeignKey("hives.id"), nullable=False, index=True)
    rule_id: Mapped[int | None] = mapped_column(ForeignKey("alert_rules.id"))
    opened_at: Mapped[datetime] = mapped_column(DataHoraUtc, nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DataHoraUtc)
    value: Mapped[float | None] = mapped_column(Float)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    hive: Mapped[Colmeia] = relationship()
