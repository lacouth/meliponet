"""Modelo de dados da plataforma.

Tres decisoes estruturais governam este modulo.

**O vinculo no <-> colmeia e historico, nao um campo.** Um no e remanejado entre
colmeias em campo: sai de uma caixa que colapsou, entra em outra. Se o vinculo fosse
uma coluna em ``nodes``, remanejar reescreveria o passado -- toda a serie historica da
colmeia antiga passaria a ser atribuida a nova. Por isso existe
:class:`NodeAssignment`, com ``installed_at``/``removed_at``, e por isso a colmeia de
uma medicao e resolvida pelo *instante da medicao*, nao pelo estado atual. Isso importa
duplamente com o spool: uma mensagem que ficou dias no buffer do no precisa pousar na
colmeia em que ele estava quando mediu.

**Metricas sao anulaveis.** Um SHT30 que falhou nao produz zero, produz *nada*. Gravar
zero apagaria a diferenca entre "a colmeia estava a 0 grau" e "nao sabemos" -- e essa
distincao e o insumo dos indicadores de completude do Edital 17.

**Propriedade e por organizacao.** O meliponicultor ve os proprios meliponarios; o
pesquisador ve todos. O escopo vive em ``meliponet.services.scope``, num helper unico,
para que nenhuma consulta o esqueca.
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator
from werkzeug.security import check_password_hash, generate_password_hash


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(UTC)


class UtcDateTime(TypeDecorator):
    """Instante sempre com fuso, em UTC, nos dois bancos suportados.

    O PostgreSQL guarda o fuso e devolve um datetime consciente; o SQLite nao guarda e
    devolve um ingenuo. Sem normalizar, o mesmo codigo se comporta de formas
    diferentes conforme o banco -- e a falha e traicoeira: comparar consciente com
    ingenuo levanta TypeError em alguns pontos, mas em outros apenas ordena errado, em
    silencio. Como a colmeia de uma leitura e resolvida comparando o instante da
    medicao com o periodo de instalacao do no, uma comparacao silenciosamente errada
    atribuiria medicoes a colmeia errada.

    Na escrita, um datetime ingenuo e recusado em vez de assumido como UTC: assumir
    esconderia justamente o bug que se quer pegar.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError(
                "datetime sem fuso horário: converta para UTC antes de gravar "
                "(veja meliponet.models.utcnow)"
            )
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class Role(enum.StrEnum):
    """Perfis de acesso.

    ``MELIPONICULTOR`` ve apenas a propria organizacao -- e o dono das colmeias.
    ``PESQUISADOR`` ve todos os dados e exporta series, porque a pesquisa depende do
    conjunto agregado. ``ADMIN`` administra cadastros e usuarios.
    """

    MELIPONICULTOR = "meliponicultor"
    PESQUISADOR = "pesquisador"
    ADMIN = "admin"

    @property
    def label(self) -> str:
        return {
            Role.MELIPONICULTOR: "Meliponicultor",
            Role.PESQUISADOR: "Pesquisador",
            Role.ADMIN: "Administrador",
        }[self]

    @property
    def sees_everything(self) -> bool:
        return self in (Role.PESQUISADOR, Role.ADMIN)


class Organization(Base):
    """Unidade de propriedade: um meliponicultor, uma associacao ou um grupo de pesquisa."""

    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)

    users: Mapped[list[User]] = relationship(back_populates="organization")
    apiaries: Mapped[list[Apiary]] = relationship(back_populates="organization")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    email: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(
        Enum(Role, native_enum=False, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=Role.MELIPONICULTOR,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(UtcDateTime)

    organization: Mapped[Organization] = relationship(back_populates="users")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    # Interface exigida pelo Flask-Login.
    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def is_anonymous(self) -> bool:
        return False

    def get_id(self) -> str:
        return str(self.id)


class Apiary(Base):
    """Um meliponario: o lugar fisico onde ficam as colmeias."""

    __tablename__ = "apiaries"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    municipality: Mapped[str | None] = mapped_column(String(120))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    #: Codigo da estacao automatica do INMET mais proxima, usado na Fase 4.
    inmet_station: Mapped[str | None] = mapped_column(String(20))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)

    organization: Mapped[Organization] = relationship(back_populates="apiaries")
    hives: Mapped[list[Hive]] = relationship(back_populates="apiary", order_by="Hive.name")


class Hive(Base):
    """Uma colmeia instrumentada."""

    __tablename__ = "hives"

    id: Mapped[int] = mapped_column(primary_key=True)
    apiary_id: Mapped[int] = mapped_column(ForeignKey("apiaries.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    #: Especies da parceria: M. scutellaris, M. subnitida e S. depilis.
    species: Mapped[str | None] = mapped_column(String(120))
    box_type: Mapped[str | None] = mapped_column(String(120))
    installed_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    notes: Mapped[str | None] = mapped_column(Text)

    apiary: Mapped[Apiary] = relationship(back_populates="hives")
    assignments: Mapped[list[NodeAssignment]] = relationship(back_populates="hive")


class Node(Base):
    """Um no MelipoSense."""

    __tablename__ = "nodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    #: Identificador do contrato: 8 digitos hexadecimais derivados do MAC do ESP32-C6.
    node_id: Mapped[str] = mapped_column(String(8), unique=True, nullable=False, index=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"))
    label: Mapped[str | None] = mapped_column(String(120))
    firmware_version: Mapped[str | None] = mapped_column(String(40))
    last_seen_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)

    organization: Mapped[Organization | None] = relationship()
    assignments: Mapped[list[NodeAssignment]] = relationship(
        back_populates="node", order_by="NodeAssignment.installed_at"
    )

    @property
    def current_assignment(self) -> NodeAssignment | None:
        for assignment in reversed(self.assignments):
            if assignment.removed_at is None:
                return assignment
        return None


class NodeAssignment(Base):
    """Periodo em que um no esteve instalado numa colmeia.

    Alem do vinculo, guarda os metadados de instalacao que o Edital 17 exige do
    protocolo: onde cada sensor foi posicionado, o registro fotografico e as condicoes
    encontradas em campo. Sao esses metadados que tornam a base curada reutilizavel por
    outro grupo -- uma serie de temperatura sem saber onde o sensor estava dentro da
    caixa nao e um dado cientifico.
    """

    __tablename__ = "node_assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    node_id: Mapped[int] = mapped_column(ForeignKey("nodes.id"), nullable=False)
    hive_id: Mapped[int] = mapped_column(ForeignKey("hives.id"), nullable=False)
    installed_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    removed_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    #: Onde cada sensor ficou: "SHT30 interno sobre o invólucro de cerume", etc.
    sensor_placement: Mapped[str | None] = mapped_column(Text)
    photo_path: Mapped[str | None] = mapped_column(String(255))
    #: Condicoes de instalacao e desvios do protocolo padrao.
    protocol_notes: Mapped[str | None] = mapped_column(Text)

    node: Mapped[Node] = relationship(back_populates="assignments")
    hive: Mapped[Hive] = relationship(back_populates="assignments")

    __table_args__ = (Index("ix_assignments_node_period", "node_id", "installed_at"),)

    def covers(self, when: datetime) -> bool:
        """Verdadeiro se ``when`` cai dentro deste periodo de instalacao."""
        if when < self.installed_at:
            return False
        return self.removed_at is None or when < self.removed_at


class Calibration(Base):
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
    applied_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False, default=utcnow)
    notes: Mapped[str | None] = mapped_column(Text)

    node: Mapped[Node] = relationship()


class AlertRule(Base):
    """Regra de deteccao de anomalia. A avaliacao entra na Fase 4."""

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


class Alert(Base):
    """Ocorrencia de uma regra. A abertura e o fechamento entram na Fase 4."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    hive_id: Mapped[int] = mapped_column(ForeignKey("hives.id"), nullable=False, index=True)
    rule_id: Mapped[int | None] = mapped_column(ForeignKey("alert_rules.id"))
    opened_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(UtcDateTime)
    value: Mapped[float | None] = mapped_column(Float)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    hive: Mapped[Hive] = relationship()


class Measurement(Base):
    """Uma leitura de telemetria ja validada e persistida."""

    __tablename__ = "measurements"

    id: Mapped[int] = mapped_column(primary_key=True)
    time: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False, index=True)
    #: Identificador do contrato, guardado como texto: uma leitura precisa continuar
    #: rastreavel ao no mesmo que o cadastro dele seja removido.
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
    received_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)

    __table_args__ = (
        # Absorve o reenvio de um no que drena o spool apos uma queda de rede: sem
        # isso a serie ganharia pontos duplicados e a completude passaria de 100%.
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

    O Edital 17 se compromete a reportar a proporcao de leituras descartadas, o que so
    e possivel se o descarte for registrado -- dai esta tabela existir desde o inicio,
    em vez de um log que some no rodizio.
    """

    __tablename__ = "ingest_rejects"

    id: Mapped[int] = mapped_column(primary_key=True)
    received_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    topic: Mapped[str | None] = mapped_column(String(200))
    node_id: Mapped[str | None] = mapped_column(String(8), index=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    #: Payload truncado, para diagnostico posterior sem inchar o banco.
    payload: Mapped[str | None] = mapped_column(Text)
