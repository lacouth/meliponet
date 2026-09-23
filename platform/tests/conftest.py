"""Configuracao e fixtures comuns dos testes da plataforma.

Poe a raiz do monorepo, ``platform/`` e ``contracts/`` no ``sys.path`` para que os
testes importem o pacote ``meliponet``, o pacote ``simulator`` e o modulo ``mensagem``
do contrato, o mesmo que o simulador usa para montar telemetria.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_DIR = REPO_ROOT / "contracts"
EXEMPLOS_DIR = CONTRACTS_DIR / "exemplos"

for path in (REPO_ROOT, REPO_ROOT / "platform", CONTRACTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from meliponet.banco import abrir_sessao, criar_tabelas, iniciar_banco  # noqa: E402
from meliponet.configuracao import Configuracao  # noqa: E402
from meliponet.modelos import (  # noqa: E402
    Colmeia,
    Meliponario,
    No,
    Organizacao,
    Perfil,
    Usuario,
    Vinculo,
)


@pytest.fixture(scope="session")
def exemplos_dir() -> Path:
    return EXEMPLOS_DIR


@pytest.fixture
def db(tmp_path):
    """Banco isolado por teste, para que um nao enxergue as linhas do outro."""
    engine = iniciar_banco(f"sqlite:///{tmp_path / 'test.sqlite3'}")
    criar_tabelas(engine)
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

    with abrir_sessao() as session:
        org = Organizacao(name="Meliponicultores da Paraíba")
        other = Organizacao(name="Cooperativa do Brejo")
        session.add_all([org, other])
        session.flush()

        meliponario = Meliponario(organization_id=org.id, name="Meliponário Mata do Buraquinho")
        outro_meliponario = Meliponario(organization_id=other.id, name="Meliponário do Brejo")
        session.add_all([meliponario, outro_meliponario])
        session.flush()

        colmeia = Colmeia(
            apiary_id=meliponario.id, name="Colmeia 01", species="Melipona scutellaris"
        )
        outra_colmeia = Colmeia(apiary_id=outro_meliponario.id, name="Colmeia alheia")
        session.add_all([colmeia, outra_colmeia])
        session.flush()

        no = No(node_id="A4C13800", organization_id=org.id)
        session.add(no)
        session.flush()

        session.add(
            Vinculo(node_id=no.id, hive_id=colmeia.id, installed_at=installed_at)
        )

        return Fixture(
            organization_id=org.id,
            other_organization_id=other.id,
            apiary_id=meliponario.id,
            hive_id=colmeia.id,
            other_hive_id=outra_colmeia.id,
            node_pk=no.id,
            node_id=no.node_id,
            installed_at=installed_at,
        )


@pytest.fixture
def make_user(db):
    """Fabrica de usuarios, para os testes de escopo montarem cada perfil."""

    def _make(
        organization_id: int,
        perfil: Perfil = Perfil.MELIPONICULTOR,
        email: str | None = None,
    ):
        with abrir_sessao() as session:
            usuario = Usuario(
                organization_id=organization_id,
                email=email or f"{perfil.value}-{organization_id}@exemplo.br",
                name=perfil.label,
                role=perfil,
            )
            usuario.set_password("senha-de-teste")
            session.add(usuario)
            session.flush()
            return usuario

    return _make


@pytest.fixture
def app(db, scenario):
    """Aplicacao Flask ligada ao banco do teste."""
    from meliponet import criar_app

    application = criar_app(
        Configuracao(
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
