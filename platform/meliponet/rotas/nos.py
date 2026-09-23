"""Instalar um no numa colmeia e retira-lo.

A tela mais importante do cadastro: e nela que os metadados de instalacao exigidos pelo
Edital 17 sao registrados -- onde cada sensor ficou dentro da caixa. As regras do
vinculo moram em ``servicos/vinculos.py``; esta rota le o formulario, confere a
permissao e chama o servico.
"""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.orm import selectinload

from meliponet.banco import sessao_do_request
from meliponet.modelos import Colmeia, agora_utc
from meliponet.rotas import formulario, permissao
from meliponet.servicos import escopo, vinculos

bp = Blueprint("nos", __name__, url_prefix="/gerenciar/no")


@bp.route("/<int:no_id>/vincular", methods=["GET", "POST"])
@login_required
def vincular(no_id: int):
    permissao.exigir_quem_administra()
    session = sessao_do_request()
    no = permissao.no_gerenciavel(session, no_id)

    if request.method == "POST":
        colmeia = permissao.colmeia_no_escopo(session, int(request.form["colmeia_id"]))

        # Em branco significa "agora", como no cadastro da colmeia; uma instalacao
        # registrada dias depois precisa da data verdadeira, porque e ela que diz a que
        # colmeia pertencem as leituras daquele intervalo.
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
    vinculo_atual = no.vinculo_atual
    if vinculo_atual is not None:
        colmeia_atual = vinculo_atual.hive.name

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
    no = permissao.no_gerenciavel(sessao_do_request(), no_id)

    if vinculos.desvincular(no):
        flash(f"Nó {no.node_id} desvinculado.", "ok")
    else:
        flash("Esse nó já está sem colmeia.", "erro")

    return redirect(url_for("cadastros.index"))
