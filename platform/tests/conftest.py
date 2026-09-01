"""Configuracao e fixtures comuns dos testes da plataforma.

Poe a raiz do monorepo e ``contracts/`` no ``sys.path`` para que os testes importem
tanto o pacote ``meliponet`` quanto o modulo ``canonical`` do contrato, compartilhado
com o gerador de vetores dourados.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_DIR = REPO_ROOT / "contracts"
TESTDATA_DIR = CONTRACTS_DIR / "testdata"

for path in (REPO_ROOT / "platform", CONTRACTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from meliponet.config import Config  # noqa: E402
from meliponet.db import create_all, init_engine, session_scope  # noqa: E402
from meliponet.models import (  # noqa: E402
    Apiary,
    Hive,
    Node,
    NodeAssignment,
    Organization,
    Role,
    User,
)


@pytest.fixture(scope="session")
def testdata_dir() -> Path:
    return TESTDATA_DIR


@pytest.fixture
def db(tmp_path):
    """Banco isolado por teste, para que um nao enxergue as linhas do outro."""
    engine = init_engine(f"sqlite:///{tmp_path / 'test.sqlite3'}")
    create_all(engine)
    return engine


@dataclass(frozen=True, slots=True)
class Fixture:
    """Ids de um cenario montado, para os testes referenciarem sem reabrir sessao."""

    organization_id: int
    other_organization_id: int
    apiary_id: int
    hive_id: int
    other_hive_id: int
    node_pk: int
    node_id: str
    installed_at: datetime


@pytest.fixture
def scenario(db) -> Fixture:
    """Duas organizacoes, uma colmeia em cada, e um no vinculado a primeira.

    Ter *duas* organizacoes desde a base e deliberado: e a unica forma de um teste
    provar que o escopo isola de verdade. Um cenario com uma organizacao so passaria
    igual com o filtro ausente.
    """
    installed_at = datetime.now(UTC) - timedelta(days=30)

    with session_scope() as session:
        org = Organization(name="Meliponicultores da Paraíba")
        other = Organization(name="Cooperativa do Brejo")
        session.add_all([org, other])
        session.flush()

        apiary = Apiary(organization_id=org.id, name="Meliponário Mata do Buraquinho")
        other_apiary = Apiary(organization_id=other.id, name="Meliponário do Brejo")
        session.add_all([apiary, other_apiary])
        session.flush()

        hive = Hive(apiary_id=apiary.id, name="Colmeia 01", species="Melipona scutellaris")
        other_hive = Hive(apiary_id=other_apiary.id, name="Colmeia alheia")
        session.add_all([hive, other_hive])
        session.flush()

        node = Node(node_id="A4C13800", organization_id=org.id)
        session.add(node)
        session.flush()

        session.add(
            NodeAssignment(node_id=node.id, hive_id=hive.id, installed_at=installed_at)
        )

        return Fixture(
            organization_id=org.id,
            other_organization_id=other.id,
            apiary_id=apiary.id,
            hive_id=hive.id,
            other_hive_id=other_hive.id,
            node_pk=node.id,
            node_id=node.node_id,
            installed_at=installed_at,
        )


@pytest.fixture
def make_user(db):
    """Fabrica de usuarios, para os testes de escopo montarem cada perfil."""

    def _make(organization_id: int, role: Role = Role.MELIPONICULTOR, email: str | None = None):
        with session_scope() as session:
            user = User(
                organization_id=organization_id,
                email=email or f"{role.value}-{organization_id}@exemplo.br",
                name=role.label,
                role=role,
            )
            user.set_password("senha-de-teste")
            session.add(user)
            session.flush()
            return user

    return _make


@pytest.fixture
def app(db, scenario):
    """Aplicacao Flask ligada ao banco do teste."""
    from meliponet import create_app

    application = create_app(
        Config(
            database_url=str(db.url),
            secret_key="teste",
            mqtt_host="localhost",
            mqtt_port=1883,
            mqtt_username=None,
            mqtt_password=None,
        )
    )
    application.config["TESTING"] = True
    return application


@pytest.fixture
def client(app):
    return app.test_client()
