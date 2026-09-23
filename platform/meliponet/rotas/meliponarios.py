"""Criar e corrigir o cadastro de um meliponario."""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from meliponet.banco import sessao_do_request
from meliponet.modelos import Meliponario
from meliponet.rotas import formulario, permissao

bp = Blueprint("meliponarios", __name__, url_prefix="/gerenciar/meliponario")


@bp.route("", methods=["POST"])
@login_required
def criar():
    permissao.exigir_quem_administra()

    meliponario = Meliponario(
        organization_id=current_user.organization_id,
        name=request.form["nome"].strip(),
        municipality=formulario.texto("municipio"),
        latitude=formulario.decimal("latitude"),
        longitude=formulario.decimal("longitude"),
    )
    sessao_do_request().add(meliponario)

    flash("Meliponário cadastrado.", "ok")
    return redirect(url_for("cadastros.index"))


@bp.route("/<int:meliponario_id>/editar", methods=["GET", "POST"])
@login_required
def editar(meliponario_id: int):
    """Corrige o cadastro de um meliponario.

    Um cadastro so criavel e um cadastro que envelhece errado: municipio digitado com
    erro, coordenada trocada de sinal, estacao do INMET descoberta depois. Nada disso
    justifica recriar o meliponario, o que orfanaria as colmeias e a serie inteira.
    """
    permissao.exigir_quem_administra()
    meliponario = permissao.meliponario_no_escopo(sessao_do_request(), meliponario_id)

    if request.method == "POST":
        meliponario.name = request.form["nome"].strip()
        meliponario.municipality = formulario.texto("municipio")
        meliponario.latitude = formulario.decimal("latitude")
        meliponario.longitude = formulario.decimal("longitude")
        meliponario.inmet_station = formulario.texto("estacao_inmet")
        meliponario.notes = formulario.texto("observacoes")
        flash("Meliponário atualizado.", "ok")
        return redirect(url_for("cadastros.index"))

    return render_template("manage/apiary_edit.html", meliponario=meliponario)
