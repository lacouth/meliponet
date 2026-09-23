"""Instalar um no numa colmeia e retira-lo.

A tela mais importante do cadastro: e nela que os metadados de instalacao exigidos pelo
Edital 17 sao registrados -- onde cada sensor ficou dentro da caixa. As regras do
vinculo moram em ``servicos/vinculos.py``; esta rota le o formulario, confere a
permissao e chama o servico.
"""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from meliponet.banco import sessao_do_request
from meliponet.modelos import Colmeia, No, agora_utc
from meliponet.rotas import formulario, permissao
from meliponet.servicos import escopo, vinculos

bp = Blueprint("nos", __name__, url_prefix="/gerenciar/no")


def _no_gerenciavel(session: Session, no_id: int) -> No:
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


@bp.route("/<int:no_id>/vincular", methods=["GET", "POST"])
@login_required
def vincular(no_id: int):
    permissao.exigir_quem_administra()
    session = sessao_do_request()
    no = _no_gerenciavel(session, no_id)

    if request.method == "POST":
        colmeia = permissao.colmeia_no_escopo(session, int(request.form["colmeia_id"]))

        instalado_em = formulario.ler_instante_local("instalado_em")
        if instalado_em is None:
            instalado_em = agora_utc()

        vinculos.vincular(
            session,
            no,
            colmeia,
            instalado_em,
            posicionamento=formulario.texto("posicionamento"),
            observacoes=formulario.texto("observacoes"),
        )
        flash(f"Nó {no.node_id} vinculado a {colmeia.name}.", "ok")
        return redirect(url_for("cadastros.index"))

    colmeias = list(
        session.scalars(
            escopo.colmeias_visiveis(current_user)
            .options(selectinload(Colmeia.apiary))
            .order_by(Colmeia.name)
        )
    )

    colmeia_atual = None
    if no.vinculo_atual is not None:
        colmeia_atual = no.vinculo_atual.hive.name

    return render_template(
        "manage/assign.html",
        no_id=no_id,
        no_label=no.node_id,
        colmeia_atual=colmeia_atual,
        colmeias=colmeias,
    )


@bp.route("/<int:no_id>/desvincular", methods=["POST"])
@login_required
def desvincular(no_id: int):
    permissao.exigir_quem_administra()
    no = _no_gerenciavel(sessao_do_request(), no_id)

    if vinculos.desvincular(no):
        flash(f"Nó {no.node_id} desvinculado.", "ok")
    else:
        flash("Esse nó já está sem colmeia.", "erro")

    return redirect(url_for("cadastros.index"))
