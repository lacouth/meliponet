"""Testes das rotas: autenticação, escopo via HTTP e cadastro.

Complementam ``test_escopo.py``. Lá a regra é testada isolada; aqui se verifica que as
rotas de fato a aplicam — a regra certa num helper que ninguém chama não protege nada.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from meliponet.banco import abrir_sessao
from meliponet.modelos import Colmeia, Medicao, Meliponario, No, Perfil, Vinculo
from sqlalchemy import select


@pytest.fixture
def login(client, make_user):
    """Autentica um usuário recém-criado e devolve-o."""

    def _login(
        organization_id: int,
        perfil: Perfil = Perfil.MELIPONICULTOR,
        email: str | None = None,
    ):
        usuario = make_user(organization_id, perfil, email)
        resposta = client.post(
            "/entrar",
            data={"email": usuario.email, "senha": "senha-de-teste"},
            follow_redirects=False,
        )
        assert resposta.status_code in (301, 302), "login deveria redirecionar"
        return usuario

    return _login


def test_paginas_exigem_login(client, scenario) -> None:
    for url in ("/colmeias", f"/colmeia/{scenario.hive_id}", "/gerenciar/"):
        resposta = client.get(url)
        assert resposta.status_code == 302, url
        assert "/entrar" in resposta.headers["Location"], url


def test_pagina_inicial_e_publica(client, scenario) -> None:
    """A raiz é o rosto do projeto: precisa abrir sem login."""
    resposta = client.get("/")
    corpo = resposta.get_data(as_text=True)

    assert resposta.status_code == 200
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
    resposta = client.get("/")

    assert resposta.status_code == 302
    assert "/colmeias" in resposta.headers["Location"]


def test_senha_errada_nao_autentica(client, scenario, make_user) -> None:
    usuario = make_user(scenario.organization_id)
    resposta = client.post("/entrar", data={"email": usuario.email, "senha": "errada"})

    assert resposta.status_code == 401
    assert client.get("/colmeias").status_code == 302


def test_email_inexistente_da_a_mesma_resposta(client, scenario) -> None:
    """Distinguir e-mail inexistente de senha errada revelaria quem tem conta."""
    resposta = client.post("/entrar", data={"email": "ninguem@exemplo.br", "senha": "x"})

    assert resposta.status_code == 401
    assert "E-mail ou senha incorretos" in resposta.get_data(as_text=True)


def test_painel_mostra_as_flags_da_ultima_leitura(client, scenario, login) -> None:
    """Uma flag e o no avisando que um sensor falhou: ela precisa chegar a tela.

    Este teste nasceu de um defeito. Na traducao do painel para o portugues, a variavel
    `latest` virou `ultima` em todo lugar menos numa condicao -- e as flags pararam de
    aparecer sem erro nenhum, porque uma variavel inexistente no Jinja vale "falso".
    """
    with abrir_sessao() as session:
        session.add(
            Medicao(
                time=datetime.now(UTC) - timedelta(minutes=1),
                node_id=scenario.node_id,
                hive_id=scenario.hive_id,
                seq=1,
                temp_in_c=30.1,
                quality_flags="sht_out_fault",
            )
        )

    login(scenario.organization_id)
    corpo = client.get(f"/colmeia/{scenario.hive_id}").get_data(as_text=True)

    assert '<span class="flag">sht_out_fault</span>' in corpo


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
    login(scenario.organization_id, Perfil.PESQUISADOR)
    corpo = client.get("/colmeias").get_data(as_text=True)

    assert "Colmeia 01" in corpo
    assert "Colmeia alheia" in corpo


def test_pesquisador_nao_cria_colmeia(client, scenario, login) -> None:
    login(scenario.organization_id, Perfil.PESQUISADOR)
    resposta = client.post(
        "/gerenciar/colmeia", data={"meliponario_id": scenario.apiary_id, "nome": "Intrusa"}
    )

    assert resposta.status_code == 403


def test_nao_se_cria_colmeia_em_meliponario_alheio(client, scenario, login) -> None:
    """Um id forjado no formulário não pode furar o escopo."""
    login(scenario.organization_id)

    with abrir_sessao() as session:
        alheio = session.get(Colmeia, scenario.other_hive_id).apiary_id

    resposta = client.post(
        "/gerenciar/colmeia", data={"meliponario_id": alheio, "nome": "Intrusa"}
    )

    assert resposta.status_code == 403


def test_vincular_no_abre_periodo_e_fecha_o_anterior(client, scenario, login) -> None:
    login(scenario.organization_id)

    with abrir_sessao() as session:
        nova = Colmeia(apiary_id=scenario.apiary_id, name="Colmeia 02")
        session.add(nova)
        session.flush()
        nova_id = nova.id

    resposta = client.post(
        f"/gerenciar/no/{scenario.node_pk}/vincular",
        data={
            "colmeia_id": nova_id,
            "posicionamento": "SHT30 interno acima do invólucro de cerume.",
        },
        follow_redirects=True,
    )
    assert resposta.status_code == 200

    with abrir_sessao() as session:
        periods = list(
            session.scalars(
                select(Vinculo)
                .where(Vinculo.node_id == scenario.node_pk)
                .order_by(Vinculo.installed_at)
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

    resposta = client.post(
        f"/gerenciar/no/{scenario.node_pk}/vincular", data={"colmeia_id": scenario.other_hive_id}
    )

    assert resposta.status_code == 403


def test_no_pendente_aparece_para_quem_administra(client, scenario, login) -> None:
    """Nó auto-cadastrado na ingestão precisa ser visível para poder ser adotado."""
    with abrir_sessao() as session:
        session.add(No(node_id="FFFFAA01"))

    login(scenario.organization_id)
    corpo = client.get("/gerenciar/").get_data(as_text=True)

    assert "FFFFAA01" in corpo


def test_admin_administra_no_de_outra_organizacao(client, scenario, login) -> None:
    """O perfil admin administra os cadastros de todas as organizações.

    É o que a documentação promete e o que a própria tela oferece: `nos_visiveis` devolve
    ao admin os nós de todas as organizações, e a tabela renderiza "Remanejar" e
    "Desvincular" para cada um. Recusar o clique depois de mostrar o botão é o pior dos
    dois mundos — a pessoa descobre a regra errando.
    """
    login(scenario.other_organization_id, Perfil.ADMIN)

    vinculo = client.post(
        f"/gerenciar/no/{scenario.node_pk}/vincular", data={"colmeia_id": scenario.hive_id}
    )
    assert vinculo.status_code == 302

    desvinculo = client.post(f"/gerenciar/no/{scenario.node_pk}/desvincular")
    assert desvinculo.status_code == 302

    with abrir_sessao() as session:
        aberto = session.scalars(
            select(Vinculo)
            .where(Vinculo.node_id == scenario.node_pk)
            .where(Vinculo.removed_at.is_(None))
        ).all()
    assert aberto == [], "o desvínculo do admin precisa fechar o período aberto"


def test_no_adotado_fica_com_a_organizacao_da_colmeia(client, scenario, login) -> None:
    """Quem clica não vira dono do nó.

    O vínculo carimbava no nó a organização de quem estava logado. Um admin adotando um
    nó para a colmeia de outra organização levava o nó junto: o dono legítimo da colmeia
    deixava de enxergar o próprio nó e não conseguia mais desvinculá-lo — sem erro
    nenhum, só um cadastro inconsistente.
    """
    with abrir_sessao() as session:
        orfao = No(node_id="FFFFAA02")
        session.add(orfao)
        session.flush()
        orfao_pk = orfao.id

    login(scenario.other_organization_id, Perfil.ADMIN)
    resposta = client.post(
        f"/gerenciar/no/{orfao_pk}/vincular", data={"colmeia_id": scenario.hive_id}
    )
    assert resposta.status_code == 302

    with abrir_sessao() as session:
        assert session.get(No, orfao_pk).organization_id == scenario.organization_id


def test_pesquisador_nao_ve_os_formularios_de_cadastro(client, scenario, login) -> None:
    """A interface precisa contar a mesma regra que a rota aplica.

    O pesquisador via os dois formulários e os botões de vínculo, e levava 403 em
    todos: descobrir a permissão errando é a pior forma de expô-la.
    """
    login(scenario.organization_id, Perfil.PESQUISADOR)
    corpo = client.get("/gerenciar/").get_data(as_text=True)

    assert "Cadastrar meliponário" not in corpo
    assert "Adicionar colmeia" not in corpo
    assert "Desvincular" not in corpo
    # E, no lugar, uma explicação — não o sumiço silencioso.
    assert "não os altera" in corpo


def test_quem_administra_continua_vendo_os_formularios(client, scenario, login) -> None:
    login(scenario.organization_id)
    corpo = client.get("/gerenciar/").get_data(as_text=True)

    assert "Cadastrar meliponário" in corpo
    assert "Adicionar colmeia" in corpo


def test_editar_meliponario(client, scenario, login) -> None:
    """Cadastro só criável envelhece errado: município com erro de digitação,
    coordenada com o sinal trocado, estação do INMET descoberta depois."""
    login(scenario.organization_id)

    resposta = client.post(
        f"/gerenciar/meliponario/{scenario.apiary_id}/editar",
        data={
            "nome": "Meliponário Mata do Buraquinho",
            "municipio": "João Pessoa",
            "latitude": "-7.1408",
            "longitude": "-34.8556",
            "estacao_inmet": "A320",
            "observacoes": "Acesso por trilha; sombreado o dia inteiro.",
        },
    )
    assert resposta.status_code == 302

    with abrir_sessao() as session:
        meliponario = session.get(Meliponario, scenario.apiary_id)
        assert meliponario.municipality == "João Pessoa"
        assert meliponario.latitude == pytest.approx(-7.1408)
        # Dois campos que, antes disto, nenhum formulário alcançava.
        assert meliponario.inmet_station == "A320"
        assert meliponario.notes.startswith("Acesso por trilha")


def test_editar_colmeia_corrige_a_data_de_instalacao(client, scenario, login) -> None:
    """A data era carimbada como "agora" no cadastro e não tinha como ser ajustada.

    Uma colmeia cadastrada semanas depois de instalada ficava com a data errada para
    sempre — e é ela que diz a partir de quando a série daquela colmeia vale.
    """
    login(scenario.organization_id)

    resposta = client.post(
        f"/gerenciar/colmeia/{scenario.hive_id}/editar",
        data={
            "nome": "Colmeia 01",
            "especie": "Melipona subnitida",
            "caixa": "INPA",
            "instalado_em": "2026-03-10T08:30",
            "observacoes": "Colônia dividida em março.",
        },
    )
    assert resposta.status_code == 302

    with abrir_sessao() as session:
        colmeia = session.get(Colmeia, scenario.hive_id)
        assert colmeia.species == "Melipona subnitida"
        assert colmeia.box_type == "INPA"
        # 08:30 na Paraíba (UTC-3) são 11:30 UTC: a data entra pelo mesmo tratamento
        # de fuso da tela de vínculo, e não deslocada em três horas.
        assert colmeia.installed_at.astimezone(UTC).hour == 11
        assert colmeia.installed_at.astimezone(UTC).day == 10


def test_nao_se_edita_cadastro_alheio(client, scenario, login) -> None:
    """Trocar o número na URL não pode virar a chave do cadastro de outra organização."""
    login(scenario.other_organization_id)

    meliponario = client.post(
        f"/gerenciar/meliponario/{scenario.apiary_id}/editar", data={"nome": "Sequestrado"}
    )
    colmeia = client.post(
        f"/gerenciar/colmeia/{scenario.hive_id}/editar", data={"nome": "Sequestrada"}
    )

    assert meliponario.status_code == 403
    assert colmeia.status_code == 403


def test_pesquisador_nao_edita_cadastro(client, scenario, login) -> None:
    login(scenario.organization_id, Perfil.PESQUISADOR)

    resposta = client.get(f"/gerenciar/colmeia/{scenario.hive_id}/editar")

    assert resposta.status_code == 403
