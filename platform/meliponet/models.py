"""Modelo de dados da plataforma.

Escopo da Fase 1 (fatia vertical): o minimo para uma medicao chegar do broker ate um
grafico -- melliponario, colmeia, no e medicao. A Fase 2 acrescenta organizacoes,
usuarios, calibracoes, regras de alerta e o historico de vinculo no <-> colmeia.

Duas decisoes que ja valem desde agora:

``measurements`` tem ``UNIQUE (node_id, seq)``
    Um no que reenvia uma mensagem do spool depois de uma queda de WiFi produz a mesma
    ``seq`` duas vezes. Sem a restricao, a serie ganharia pontos duplicados; com ela, o
    reenvio e um no-op idempotente. E o que torna seguro o "reenvie o que ficou na
    fila" do firmware.

Metricas sao anulaveis
    Um SHT30 que falhou nao produz zero, produz *nada*. Gravar zero apagaria a
    diferenca entre "a colmeia estava a 0 grau" e "nao sabemos a temperatura" -- e essa
    distincao e o insumo dos indicadores de completude do Edital 17.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Apiary(Base):
    """Um meliponario: o lugar fisico onde ficam as colmeias."""

    __tablename__ = "apiaries"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    municipality: Mapped[str | None] = mapped_column(String(120))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    hives: Mapped[list[Hive]] = relationship(back_populates="apiary", order_by="Hive.name")


class Hive(Base):
    """Uma colmeia instrumentada."""

    __tablename__ = "hives"

    id: Mapped[int] = mapped_column(primary_key=True)
    apiary_id: Mapped[int] = mapped_column(ForeignKey("apiaries.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    #: Especie-alvo. As tres da parceria sao M. scutellaris, M. subnitida e S. depilis.
    species: Mapped[str | None] = mapped_column(String(120))
    box_type: Mapped[str | None] = mapped_column(String(120))
    installed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    apiary: Mapped[Apiary] = relationship(back_populates="hives")
    nodes: Mapped[list[Node]] = relationship(back_populates="hive")


class Node(Base):
    """Um no MelipoSense.

    O vinculo com a colmeia esta aqui, direto, apenas na Fase 1. A Fase 2 o move para
    ``node_assignments`` com ``installed_at``/``removed_at``, porque um no e remanejado
    entre colmeias em campo e, sem esse historico, as series de uma colmeia ficariam
    contaminadas com leituras de outra.
    """

    __tablename__ = "nodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    #: Identificador do contrato: 8 digitos hexadecimais derivados do MAC do ESP32-C6.
    node_id: Mapped[str] = mapped_column(String(8), unique=True, nullable=False, index=True)
    hive_id: Mapped[int | None] = mapped_column(ForeignKey("hives.id"))
    label: Mapped[str | None] = mapped_column(String(120))
    firmware_version: Mapped[str | None] = mapped_column(String(40))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    hive: Mapped[Hive | None] = relationship(back_populates="nodes")


class Measurement(Base):
    """Uma leitura de telemetria ja validada e persistida."""

    __tablename__ = "measurements"

    id: Mapped[int] = mapped_column(primary_key=True)
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    node_id: Mapped[str] = mapped_column(String(8), nullable=False)
    hive_id: Mapped[int | None] = mapped_column(ForeignKey("hives.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)

    temp_in_c: Mapped[float | None] = mapped_column(Float)
    temp_out_c: Mapped[float | None] = mapped_column(Float)
    rh_in_pct: Mapped[float | None] = mapped_column(Float)
    rh_out_pct: Mapped[float | None] = mapped_column(Float)
    weight_kg: Mapped[float | None] = mapped_column(Float)
    vbat_v: Mapped[float | None] = mapped_column(Float)
    rssi: Mapped[int | None] = mapped_column(Integer)

    # Colunas da Fase 5 criadas desde ja, nulas ate existir um no com INMP441. Um no
    # completo entrando em campo nao deve exigir migracao de esquema.
    snr: Mapped[float | None] = mapped_column(Float)
    sound_rms: Mapped[float | None] = mapped_column(Float)

    gateway_id: Mapped[str | None] = mapped_column(String(32))
    #: Flags do no e da validacao semantica, separadas por virgula.
    quality_flags: Mapped[str | None] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        UniqueConstraint("node_id", "seq", name="uq_measurements_node_seq"),
        Index("ix_measurements_hive_time", "hive_id", "time"),
    )

    @property
    def thermal_differential_c(self) -> float | None:
        """Esforco termorregulatorio estimado: interna menos externa."""
        if self.temp_in_c is None or self.temp_out_c is None:
            return None
        return self.temp_in_c - self.temp_out_c


class IngestReject(Base):
    """Mensagem recusada na ingestao, com o motivo.

    O Edital 17 se compromete a reportar a proporcao de leituras descartadas. Isso so e
    possivel se o descarte for registrado -- dai esta tabela existir desde a Fase 1, e
    nao ser um log que some no rodizio.
    """

    __tablename__ = "ingest_rejects"

    id: Mapped[int] = mapped_column(primary_key=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    topic: Mapped[str | None] = mapped_column(String(200))
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    #: Payload truncado, para diagnostico posterior sem inchar o banco.
    payload: Mapped[str | None] = mapped_column(Text)
