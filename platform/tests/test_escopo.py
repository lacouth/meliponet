"""Testes do isolamento por organização.

Estes são os testes mais importantes da Fase 2, porque o modo de falha do escopo é o
silêncio: uma consulta que esquece o filtro não quebra, não levanta erro e passa em
qualquer teste de rota que só verifique o status HTTP. Ela apenas mostra a um
meliponicultor as colmeias de outro.

Por isso o cenário-base tem **duas** organizações. Com uma só, todo teste aqui passaria
igual com o filtro removido.
"""

from __future__ import annotations

import pytest
from meliponet.banco import abrir_sessao
from meliponet.modelos import Colmeia, Meliponario, No, Perfil
from meliponet.servicos import escopo


@pytest.fixture
def meliponicultor(cenario, criar_usuario):
    return criar_usuario(cenario.organizacao_id, Perfil.MELIPONICULTOR)


@pytest.fixture
def pesquisador(cenario, criar_usuario):
    return criar_usuario(cenario.organizacao_id, Perfil.PESQUISADOR)


@pytest.fixture
def dono_alheio(cenario, criar_usuario):
    return criar_usuario(cenario.outra_organizacao_id, Perfil.MELIPONICULTOR)


def test_meliponicultor_ve_apenas_a_propria_organizacao(cenario, meliponicultor) -> None:
    with abrir_sessao() as session:
        hives = list(session.scalars(escopo.colmeias_visiveis(meliponicultor)))
        apiaries = list(session.scalars(escopo.meliponarios_visiveis(meliponicultor)))

    assert [h.id for h in hives] == [cenario.colmeia_id]
    assert all(a.organization_id == cenario.organizacao_id for a in apiaries)


def test_pesquisador_ve_todas_as_colmeias(cenario, pesquisador) -> None:
    """A pesquisa depende do conjunto agregado, não de um meliponário isolado."""
    with abrir_sessao() as session:
        hives = list(session.scalars(escopo.colmeias_visiveis(pesquisador)))

    assert {h.id for h in hives} == {cenario.colmeia_id, cenario.outra_colmeia_id}


def test_colmeia_alheia_nao_e_visivel(cenario, meliponicultor, dono_alheio) -> None:
    with abrir_sessao() as session:
        assert escopo.pode_ver_colmeia(session, meliponicultor, cenario.colmeia_id)
        assert not escopo.pode_ver_colmeia(session, meliponicultor, cenario.outra_colmeia_id)
        # E o recíproco: o isolamento vale nos dois sentidos.
        assert escopo.pode_ver_colmeia(session, dono_alheio, cenario.outra_colmeia_id)
        assert not escopo.pode_ver_colmeia(session, dono_alheio, cenario.colmeia_id)


def test_pesquisador_nao_edita_cadastros(pesquisador, meliponicultor) -> None:
    """Visão ampla é de leitura.

    Uma análise não pode alterar por engano o cadastro de campo de outra pessoa — quem
    instalou o nó na caixa é quem sabe onde cada sensor ficou.
    """
    assert escopo.pode_gerenciar(meliponicultor)
    assert not escopo.pode_gerenciar(pesquisador)


def test_escopo_acompanha_colmeia_nova(cenario, meliponicultor) -> None:
    """Uma colmeia criada depois entra no escopo pelo meliponário, sem ajuste manual."""
    with abrir_sessao() as session:
        meliponario = session.get(Meliponario, cenario.meliponario_id)
        session.add(Colmeia(apiary_id=meliponario.id, name="Colmeia 02"))

    with abrir_sessao() as session:
        hives = list(session.scalars(escopo.colmeias_visiveis(meliponicultor)))

    assert {h.name for h in hives} == {"Colmeia 01", "Colmeia 02"}


@pytest.fixture
def admin(cenario, criar_usuario):
    return criar_usuario(cenario.organizacao_id, Perfil.ADMIN)


def test_admin_administra_no_de_qualquer_organizacao(
    cenario, admin, meliponicultor, dono_alheio
) -> None:
    """Ver tudo e poder administrar tudo andam juntos para o admin.

    O meliponicultor continua alcançando só o próprio nó — é este par de asserções que
    impede a correção de virar um buraco no isolamento.
    """
    with abrir_sessao() as session:
        assert escopo.pode_gerenciar_no(session, admin, cenario.no_pk)
        assert escopo.pode_gerenciar_no(session, meliponicultor, cenario.no_pk)
        assert not escopo.pode_gerenciar_no(session, dono_alheio, cenario.no_pk)


def test_no_sem_dono_e_adotavel_por_quem_administra(
    cenario, admin, meliponicultor, dono_alheio
) -> None:
    """Adotar um nó recém-aparecido é a operação que lhe dá organização.

    Enquanto ele não tem dono, exigir que já pertença a alguém tornaria a adoção
    impossível — e o nó publicaria para sempre sem aparecer em gráfico nenhum.
    """
    with abrir_sessao() as session:
        orfao = No(node_id="FFFFAA03")
        session.add(orfao)
        session.flush()
        orfao_pk = orfao.id

    with abrir_sessao() as session:
        assert escopo.pode_gerenciar_no(session, admin, orfao_pk)
        assert escopo.pode_gerenciar_no(session, meliponicultor, orfao_pk)
        assert escopo.pode_gerenciar_no(session, dono_alheio, orfao_pk)
