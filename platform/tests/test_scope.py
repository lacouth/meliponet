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
from meliponet.db import session_scope
from meliponet.models import Apiary, Hive, Role
from meliponet.services import scope


@pytest.fixture
def meliponicultor(scenario, make_user):
    return make_user(scenario.organization_id, Role.MELIPONICULTOR)


@pytest.fixture
def pesquisador(scenario, make_user):
    return make_user(scenario.organization_id, Role.PESQUISADOR)


@pytest.fixture
def dono_alheio(scenario, make_user):
    return make_user(scenario.other_organization_id, Role.MELIPONICULTOR)


def test_meliponicultor_ve_apenas_a_propria_organizacao(scenario, meliponicultor) -> None:
    with session_scope() as session:
        hives = list(session.scalars(scope.hives_for(meliponicultor)))
        apiaries = list(session.scalars(scope.apiaries_for(meliponicultor)))

    assert [h.id for h in hives] == [scenario.hive_id]
    assert all(a.organization_id == scenario.organization_id for a in apiaries)


def test_pesquisador_ve_todas_as_colmeias(scenario, pesquisador) -> None:
    """A pesquisa depende do conjunto agregado, não de um meliponário isolado."""
    with session_scope() as session:
        hives = list(session.scalars(scope.hives_for(pesquisador)))

    assert {h.id for h in hives} == {scenario.hive_id, scenario.other_hive_id}


def test_colmeia_alheia_nao_e_visivel(scenario, meliponicultor, dono_alheio) -> None:
    with session_scope() as session:
        assert scope.can_view_hive(session, meliponicultor, scenario.hive_id)
        assert not scope.can_view_hive(session, meliponicultor, scenario.other_hive_id)
        # E o recíproco: o isolamento vale nos dois sentidos.
        assert scope.can_view_hive(session, dono_alheio, scenario.other_hive_id)
        assert not scope.can_view_hive(session, dono_alheio, scenario.hive_id)


def test_pesquisador_nao_edita_cadastros(pesquisador, meliponicultor) -> None:
    """Visão ampla é de leitura.

    Uma análise não pode alterar por engano o cadastro de campo de outra pessoa — quem
    instalou o nó na caixa é quem sabe onde cada sensor ficou.
    """
    assert scope.can_manage(meliponicultor)
    assert not scope.can_manage(pesquisador)


def test_escopo_acompanha_colmeia_nova(scenario, meliponicultor) -> None:
    """Uma colmeia criada depois entra no escopo pelo meliponário, sem ajuste manual."""
    with session_scope() as session:
        apiary = session.get(Apiary, scenario.apiary_id)
        session.add(Hive(apiary_id=apiary.id, name="Colmeia 02"))

    with session_scope() as session:
        hives = list(session.scalars(scope.hives_for(meliponicultor)))

    assert {h.name for h in hives} == {"Colmeia 01", "Colmeia 02"}
