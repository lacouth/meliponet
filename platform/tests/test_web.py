"""Testes das rotas: autenticação, escopo via HTTP e cadastro.

Complementam ``test_scope.py``. Lá a regra é testada isolada; aqui se verifica que as
rotas de fato a aplicam — a regra certa num helper que ninguém chama não protege nada.
"""

from __future__ import annotations

import pytest
from meliponet.db import session_scope
from meliponet.models import Hive, Node, NodeAssignment, Role
from sqlalchemy import select


@pytest.fixture
def login(client, make_user):
    """Autentica um usuário recém-criado e devolve-o."""

    def _login(organization_id: int, role: Role = Role.MELIPONICULTOR, email: str | None = None):
        user = make_user(organization_id, role, email)
        response = client.post(
            "/entrar",
            data={"email": user.email, "senha": "senha-de-teste"},
            follow_redirects=False,
        )
        assert response.status_code in (301, 302), "login deveria redirecionar"
        return user

    return _login


def test_paginas_exigem_login(client, scenario) -> None:
    for url in ("/colmeias", f"/colmeia/{scenario.hive_id}", "/gerenciar/"):
        response = client.get(url)
        assert response.status_code == 302, url
        assert "/entrar" in response.headers["Location"], url


def test_pagina_inicial_e_publica(client, scenario) -> None:
    """A raiz é o rosto do projeto: precisa abrir sem login."""
    response = client.get("/")
    corpo = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "sem precisar abri-la" in corpo
    assert "/entrar" in corpo


def test_pagina_inicial_nao_vaza_dados_de_colmeia(client, scenario) -> None:
    """Só agregados. Nome ou localização de colmeia não podem aparecer a anônimos."""
    corpo = client.get("/").get_data(as_text=True)

    assert "Colmeia 01" not in corpo
    assert "Colmeia alheia" not in corpo
    assert "Meliponário Mata do Buraquinho" not in corpo


def test_usuario_autenticado_vai_para_o_painel(client, scenario, login) -> None:
    login(scenario.organization_id)
    response = client.get("/")

    assert response.status_code == 302
    assert "/colmeias" in response.headers["Location"]


def test_senha_errada_nao_autentica(client, scenario, make_user) -> None:
    user = make_user(scenario.organization_id)
    response = client.post("/entrar", data={"email": user.email, "senha": "errada"})

    assert response.status_code == 401
    assert client.get("/colmeias").status_code == 302


def test_email_inexistente_da_a_mesma_resposta(client, scenario) -> None:
    """Distinguir e-mail inexistente de senha errada revelaria quem tem conta."""
    response = client.post("/entrar", data={"email": "ninguem@exemplo.br", "senha": "x"})

    assert response.status_code == 401
    assert "E-mail ou senha incorretos" in response.get_data(as_text=True)


def test_colmeia_alheia_responde_404(client, scenario, login) -> None:
    """404, e não 403.

    Um 403 confirmaria que aquele id existe, e enumerar ids é justamente o ataque que
    a rota precisa impedir.
    """
    login(scenario.organization_id)

    assert client.get(f"/colmeia/{scenario.hive_id}").status_code == 200
    assert client.get(f"/colmeia/{scenario.other_hive_id}").status_code == 404
    assert client.get("/colmeia/99999").status_code == 404


def test_dashboard_lista_apenas_colmeias_proprias(client, scenario, login) -> None:
    login(scenario.organization_id)
    corpo = client.get("/colmeias").get_data(as_text=True)

    assert "Colmeia 01" in corpo
    assert "Colmeia alheia" not in corpo


def test_pesquisador_ve_as_duas(client, scenario, login) -> None:
    login(scenario.organization_id, Role.PESQUISADOR)
    corpo = client.get("/colmeias").get_data(as_text=True)

    assert "Colmeia 01" in corpo
    assert "Colmeia alheia" in corpo


def test_pesquisador_nao_cria_colmeia(client, scenario, login) -> None:
    login(scenario.organization_id, Role.PESQUISADOR)
    response = client.post(
        "/gerenciar/colmeia", data={"meliponario_id": scenario.apiary_id, "nome": "Intrusa"}
    )

    assert response.status_code == 403


def test_nao_se_cria_colmeia_em_meliponario_alheio(client, scenario, login) -> None:
    """Um id forjado no formulário não pode furar o escopo."""
    login(scenario.organization_id)

    with session_scope() as session:
        alheio = session.get(Hive, scenario.other_hive_id).apiary_id

    response = client.post(
        "/gerenciar/colmeia", data={"meliponario_id": alheio, "nome": "Intrusa"}
    )

    assert response.status_code == 403


def test_vincular_no_abre_periodo_e_fecha_o_anterior(client, scenario, login) -> None:
    login(scenario.organization_id)

    with session_scope() as session:
        nova = Hive(apiary_id=scenario.apiary_id, name="Colmeia 02")
        session.add(nova)
        session.flush()
        nova_id = nova.id

    response = client.post(
        f"/gerenciar/no/{scenario.node_pk}/vincular",
        data={
            "colmeia_id": nova_id,
            "posicionamento": "SHT30 interno acima do invólucro de cerume.",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    with session_scope() as session:
        periods = list(
            session.scalars(
                select(NodeAssignment)
                .where(NodeAssignment.node_id == scenario.node_pk)
                .order_by(NodeAssignment.installed_at)
            )
        )

    assert len(periods) == 2
    # O vínculo antigo é encerrado, não apagado: as leituras já gravadas continuam
    # apontando para a colmeia em que o nó estava quando mediu.
    assert periods[0].hive_id == scenario.hive_id
    assert periods[0].removed_at is not None
    assert periods[1].hive_id == nova_id
    assert periods[1].removed_at is None
    assert "invólucro de cerume" in (periods[1].sensor_placement or "")


def test_no_alheio_nao_pode_ser_vinculado(client, scenario, login) -> None:
    login(scenario.other_organization_id)

    response = client.post(
        f"/gerenciar/no/{scenario.node_pk}/vincular", data={"colmeia_id": scenario.other_hive_id}
    )

    assert response.status_code == 403


def test_no_pendente_aparece_para_quem_administra(client, scenario, login) -> None:
    """Nó auto-cadastrado na ingestão precisa ser visível para poder ser adotado."""
    with session_scope() as session:
        session.add(Node(node_id="FFFFAA01"))

    login(scenario.organization_id)
    corpo = client.get("/gerenciar/").get_data(as_text=True)

    assert "FFFFAA01" in corpo
