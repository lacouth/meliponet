"""Autenticacao."""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import select

from meliponet.db import session_scope
from meliponet.models import User, utcnow

bp = Blueprint("auth", __name__)


@bp.route("/entrar", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("senha") or ""

        with session_scope() as session:
            user = session.scalar(select(User).where(User.email == email))
            # Mensagem unica para email inexistente e senha errada: distinguir os dois
            # casos revelaria quais enderecos tem conta na plataforma.
            if user is None or not user.is_active or not user.check_password(password):
                flash("E-mail ou senha incorretos.", "erro")
                return render_template("auth/login.html", email=email), 401

            user.last_login_at = utcnow()
            login_user(user, remember=True)

        return redirect(request.args.get("next") or url_for("dashboard.index"))

    return render_template("auth/login.html", email="")


@bp.route("/sair")
@login_required
def logout():
    logout_user()
    flash("Sessão encerrada.", "ok")
    return redirect(url_for("auth.login"))
