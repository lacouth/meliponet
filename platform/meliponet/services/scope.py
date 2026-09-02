"""Escopo de visibilidade por usuario.

Todo acesso a dados de colmeia passa por aqui. A razao de existir um helper unico, em
vez de um ``WHERE organization_id = ...`` espalhado pelas views, e que o modo de falha
desse tipo de regra e o silencio: uma consulta que esquece o filtro nao quebra, nao
levanta erro e nao aparece em teste de rota -- ela apenas mostra a um meliponicultor as
colmeias de outro. Concentrando a regra num lugar, esquecer passa a ser dificil, e a
regra fica testavel isoladamente.

Os perfis:

``MELIPONICULTOR``
    Ve apenas o que pertence a propria organizacao. E o dono das colmeias.
``PESQUISADOR``
    Ve tudo. A pesquisa depende do conjunto agregado -- correlacionar clima e colmeia
    exige as series de todos os meliponarios, nao de um.
``ADMIN``
    Ve tudo e administra cadastros e usuarios.
"""

from __future__ import annotations

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from meliponet.models import Apiary, Hive, Node, Role, User


def apiaries_for(user: User) -> Select[tuple[Apiary]]:
    """Meliponarios visiveis ao usuario."""
    statement = select(Apiary)
    if not user.role.sees_everything:
        statement = statement.where(Apiary.organization_id == user.organization_id)
    return statement


def hives_for(user: User) -> Select[tuple[Hive]]:
    """Colmeias visiveis ao usuario."""
    statement = select(Hive).join(Apiary, Hive.apiary_id == Apiary.id)
    if not user.role.sees_everything:
        statement = statement.where(Apiary.organization_id == user.organization_id)
    return statement


def nodes_for(user: User) -> Select[tuple[Node]]:
    """Nos visiveis ao usuario.

    Nos sem organizacao -- auto-cadastrados na primeira telemetria -- so aparecem para
    quem administra, que e quem pode vincula-los a uma colmeia.
    """
    statement = select(Node)
    if not user.role.sees_everything:
        statement = statement.where(Node.organization_id == user.organization_id)
    return statement


def manageable_nodes_for(user: User) -> Select[tuple[Node]]:
    """Nos que o usuario pode vincular ou desvincular.

    E ``nodes_for`` mais os nos ainda sem dono: adotar um no recem-aparecido e
    justamente a operacao que lhe da organizacao, entao exigir que ele ja pertenca a
    alguem tornaria a adocao impossivel.

    Existe aqui, e nao como um ``if`` na view, pela razao do modulo inteiro: a
    comparacao escrita a mao la dentro nao acompanhou os perfis que veem tudo, e o
    administrador passou a receber 403 nos nos que a propria tela lhe mostrava.
    """
    statement = select(Node)
    if not user.role.sees_everything:
        statement = statement.where(
            or_(
                Node.organization_id == user.organization_id,
                Node.organization_id.is_(None),
            )
        )
    return statement


def can_view_hive(session: Session, user: User, hive_id: int) -> bool:
    """Autorizacao de acesso a uma colmeia especifica.

    Usada nas rotas que recebem o id pela URL. Sem esta checagem, trocar o numero no
    endereco seria suficiente para ler a colmeia de outra organizacao.
    """
    return session.scalar(hives_for(user).where(Hive.id == hive_id).limit(1)) is not None


def can_manage_node(session: Session, user: User, node_id: int) -> bool:
    """Autorizacao para vincular ou desvincular um no especifico.

    Irma de ``can_view_hive``, para as rotas que recebem o id do no pela URL.
    """
    return (
        session.scalar(manageable_nodes_for(user).where(Node.id == node_id).limit(1))
        is not None
    )


def can_manage(user: User) -> bool:
    """Se o usuario pode criar e editar cadastros.

    O meliponicultor administra os proprios meliponarios: e ele quem instala o no na
    caixa e sabe onde cada sensor ficou. O pesquisador tem visao ampla mas de leitura,
    para que uma analise nao altere por engano o cadastro de campo de outra pessoa.

    Esta funcao responde apenas *se* o usuario administra, nunca *o que* ele alcanca --
    isso e das consultas de escopo acima. O meliponicultor administra a propria
    organizacao; o admin, todas.
    """
    return user.role in (Role.MELIPONICULTOR, Role.ADMIN)
