"""Autenticacao."""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import select

from meliponet.banco import sessao_do_request
from meliponet.modelos import Usuario, agora_utc

bp = Blueprint("autenticacao", __name__)


@bp.route("/entrar", methods=["GET", "POST"])
def entrar():
    if current_user.is_authenticated:
        return redirect(url_for("painel.index"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        senha = request.form.get("senha") or ""

        session = sessao_do_request()
        usuario = session.scalar(select(Usuario).where(Usuario.email == email))
        # Mensagem unica para email inexistente e senha errada: distinguir os dois
        # casos revelaria quais enderecos tem conta na plataforma.
        if usuario is None or not usuario.is_active or not usuario.check_password(senha):
            flash("E-mail ou senha incorretos.", "erro")
            return render_template("autenticacao/entrar.html", email=email), 401

        usuario.last_login_at = agora_utc()
        login_user(usuario, remember=True)

        return redirect(request.args.get("next") or url_for("painel.index"))

    return render_template("autenticacao/entrar.html", email="")


@bp.route("/sair")
@login_required
def sair():
    logout_user()
    flash("Sessão encerrada.", "ok")
    return redirect(url_for("autenticacao.entrar"))
