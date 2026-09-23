"""Checagens de permissao das telas de cadastro, que interrompem com 403 (ou 404).

A regra de quem ve o que mora em ``servicos/escopo.py``. Aqui ficam so os ajudantes que
aplicam essa regra numa rota: carregam o objeto pedido e interrompem a requisicao se o
usuario nao puder mexer nele. Esquecer a checagem nao quebra nada -- apenas deixa um id
forjado alcancar o cadastro de outra organizacao --, por isso ela tem nome e um lugar so.
"""

from flask import abort
from flask_login import current_user
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from meliponet.modelos import Colmeia, Meliponario, No
from meliponet.servicos import escopo


def exigir_quem_administra() -> None:
    """Interrompe com 403 se o usuario so tem leitura (o pesquisador)."""
    if not escopo.pode_gerenciar(current_user):
        abort(403)


def meliponario_no_escopo(session: Session, meliponario_id: int) -> Meliponario:
    """Carrega o meliponario, exigindo que ele seja visivel ao usuario."""
    meliponario = session.scalar(
        escopo.meliponarios_visiveis(current_user).where(Meliponario.id == meliponario_id)
    )
    if meliponario is None:
        abort(403)
    return meliponario


def colmeia_no_escopo(session: Session, colmeia_id: int) -> Colmeia:
    """Carrega a colmeia, exigindo que ela seja visivel ao usuario."""
    colmeia = session.scalar(
        escopo.colmeias_visiveis(current_user).where(Colmeia.id == colmeia_id)
    )
    if colmeia is None:
        abort(403)
    return colmeia


def no_gerenciavel(session: Session, no_id: int) -> No:
    """Carrega o no que o usuario pode vincular ou desvincular.

    Um no que nao existe e 404; um que existe mas nao e seu e 403. Um no ainda sem dono
    pode ser adotado por quem administra; um no de outra organizacao, so por quem
    administra todas -- a regra inteira mora em ``escopo.pode_gerenciar_no``.
    """
    no = session.scalar(select(No).options(selectinload(No.assignments)).where(No.id == no_id))
    if no is None:
        abort(404)
    if not escopo.pode_gerenciar_no(session, current_user, no.id):
        abort(403)
    return no
