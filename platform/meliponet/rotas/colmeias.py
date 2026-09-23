"""Criar e corrigir o cadastro de uma colmeia.

A tela de *ver* uma colmeia, com os graficos, fica em ``painel.py``; aqui fica so o
cadastro.
"""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from meliponet.banco import sessao_do_request
from meliponet.configuracao import NOMES_CIENTIFICOS
from meliponet.modelos import Colmeia, agora_utc
from meliponet.rotas import formulario, permissao

bp = Blueprint("colmeias", __name__, url_prefix="/gerenciar/colmeia")


@bp.route("", methods=["POST"])
@login_required
def criar():
    permissao.exigir_quem_administra()
    session = sessao_do_request()
    meliponario = permissao.meliponario_no_escopo(session, int(request.form["meliponario_id"]))

    # Em branco significa "agora", que e o caso comum; mas uma colmeia cadastrada
    # semanas depois de instalada precisa da data verdadeira, e e ela que delimita a
    # serie da colmeia.
    instalado_em = formulario.ler_instante_local("instalado_em")
    if instalado_em is None:
        instalado_em = agora_utc()

    colmeia = Colmeia(
        apiary_id=meliponario.id,
        name=request.form["nome"].strip(),
        species=formulario.texto("especie"),
        box_type=formulario.texto("caixa"),
        installed_at=instalado_em,
    )
    session.add(colmeia)

    flash("Colmeia cadastrada.", "ok")
    return redirect(url_for("cadastros.index"))


@bp.route("/<int:colmeia_id>/editar", methods=["GET", "POST"])
@login_required
def editar(colmeia_id: int):
    """Corrige o cadastro de uma colmeia, inclusive a data de instalacao.

    E a data de instalacao que diz a partir de quando a serie daquela colmeia comeca a
    valer -- por isso ela precisa poder ser corrigida depois.
    """
    permissao.exigir_quem_administra()
    colmeia = permissao.colmeia_no_escopo(sessao_do_request(), colmeia_id)

    if request.method == "POST":
        colmeia.name = request.form["nome"].strip()
        colmeia.species = formulario.texto("especie")
        colmeia.box_type = formulario.texto("caixa")
        colmeia.installed_at = formulario.ler_instante_local("instalado_em")
        colmeia.notes = formulario.texto("observacoes")
        flash("Colmeia atualizada.", "ok")
        return redirect(url_for("cadastros.index"))

    return render_template(
        "colmeias/editar.html",
        colmeia=colmeia,
        # O campo `datetime-local` do HTML tem formato proprio, e a conversao e da
        # rota: o template escreve o que recebe, sem saber de fuso.
        instalado_em=formulario.escrever_instante_local(colmeia.installed_at),
        especies=NOMES_CIENTIFICOS,
    )
