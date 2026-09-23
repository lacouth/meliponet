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


@dataclass
class Cenario:
    """Ids de um cenario montado, para os testes referenciarem sem reabrir sessao.

    `no_pk` e a chave do no no banco (a coluna `id`); `node_id` e o identificador do
    contrato, o que o no escreve na mensagem ("A4C13800").
    """

    organizacao_id: int
    outra_organizacao_id: int
    meliponario_id: int
    colmeia_id: int
    outra_colmeia_id: int
    no_pk: int
    node_id: str
    instalado_em: datetime


@pytest.fixture
def cenario(db) -> Cenario:
    """Duas organizacoes, uma colmeia em cada, e um no vinculado a primeira.

    Ter *duas* organizacoes desde a base e deliberado: e a unica forma de um teste
    provar que o escopo isola de verdade. Um cenario com uma organizacao so passaria
    igual com o filtro ausente.
    """
    instalado_em = datetime.now(UTC) - timedelta(days=30)

    with abrir_sessao() as session:
        organizacao = Organizacao(name="Meliponicultores da Paraíba")
        outra = Organizacao(name="Cooperativa do Brejo")
        session.add_all([organizacao, outra])
        session.flush()

        meliponario = Meliponario(
            organization_id=organizacao.id, name="Meliponário Mata do Buraquinho"
        )
        outro_meliponario = Meliponario(organization_id=outra.id, name="Meliponário do Brejo")
        session.add_all([meliponario, outro_meliponario])
        session.flush()

        colmeia = Colmeia(
            apiary_id=meliponario.id, name="Colmeia 01", species="Melipona scutellaris"
        )
        outra_colmeia = Colmeia(apiary_id=outro_meliponario.id, name="Colmeia alheia")
        session.add_all([colmeia, outra_colmeia])
        session.flush()

        no = No(node_id="A4C13800", organization_id=organizacao.id)
        session.add(no)
        session.flush()

        session.add(
            Vinculo(node_id=no.id, hive_id=colmeia.id, installed_at=instalado_em)
        )

        return Cenario(
            organizacao_id=organizacao.id,
            outra_organizacao_id=outra.id,
            meliponario_id=meliponario.id,
            colmeia_id=colmeia.id,
            outra_colmeia_id=outra_colmeia.id,
            no_pk=no.id,
            node_id=no.node_id,
            instalado_em=instalado_em,
        )


@pytest.fixture
def criar_usuario(db):
    """Fabrica de usuarios, para os testes de escopo montarem cada perfil."""

    def _criar(
        organizacao_id: int,
        perfil: Perfil = Perfil.MELIPONICULTOR,
        email: str | None = None,
    ):
        with abrir_sessao() as session:
            usuario = Usuario(
                organization_id=organizacao_id,
                email=email or f"{perfil.value}-{organizacao_id}@exemplo.br",
                name=perfil.label,
                role=perfil,
            )
            usuario.set_password("senha-de-teste")
            session.add(usuario)
            session.flush()
            return usuario

    return _criar


@pytest.fixture
def app(db, cenario):
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
