"""Pagina inicial publica.

E a unica pagina da plataforma que nao exige login: o rosto do projeto para o
meliponicultor que recebeu o endereco, para o avaliador do edital e para quem chega por
um trabalho apresentado no SIMPIF.

Sobre os numeros exibidos: sao **apenas agregados** -- quantas colmeias, quantos
meliponarios, quantas medicoes. Nunca nomes, localizacoes ou leituras.
"""

from __future__ import annotations

from flask import Blueprint, redirect, render_template, url_for
from flask_login import current_user
from sqlalchemy import func, select

from meliponet.banco import sessao_do_request
from meliponet.modelos import Colmeia, Medicao, Meliponario, No

bp = Blueprint("publico", __name__)

#: Especies-alvo da parceria, com o nome popular pelo qual o meliponicultor as conhece.
ESPECIES = [
    ("Melipona scutellaris", "uruçu-nordestina"),
    ("Melipona subnitida", "jandaíra"),
    ("Scaptotrigona depilis", "canudo"),
]


def _quantos(session, modelo) -> int:
    """Quantas linhas existem de ``modelo``."""
    return session.scalar(select(func.count()).select_from(modelo)) or 0


@bp.route("/")
def index():
    # Quem ja esta autenticado quer o painel, nao a apresentacao do projeto.
    if current_user.is_authenticated:
        return redirect(url_for("painel.index"))

    session = sessao_do_request()
    numeros = {
        "hives": _quantos(session, Colmeia),
        "apiaries": _quantos(session, Meliponario),
        "measurements": _quantos(session, Medicao),
        "nodes": _quantos(session, No),
    }

    return render_template("public/index.html", numeros=numeros, especies=ESPECIES)
