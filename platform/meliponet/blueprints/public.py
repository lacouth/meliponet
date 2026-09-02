"""Pagina inicial publica.

E a unica pagina da plataforma que nao exige login: o rosto do projeto para o
meliponicultor que recebeu o endereco, para o avaliador do edital e para quem chega por
um trabalho apresentado no SIMPIF.

Sobre os numeros exibidos: sao **apenas agregados** -- quantas colmeias, quantos
meliponarios, quantas medicoes. Nunca nomes, localizacoes ou leituras. A contagem
demonstra que o sistema esta vivo e coletando, que e o que interessa a quem chega aqui,
sem expor a nenhum visitante anonimo onde ficam as colmeias de um produtor.
"""

from __future__ import annotations

from flask import Blueprint, redirect, render_template, url_for
from flask_login import current_user
from sqlalchemy import func, select

from meliponet.db import session_scope
from meliponet.models import Apiary, Hive, Measurement, Node

bp = Blueprint("public", __name__)

#: Especies-alvo da parceria, com o nome popular pelo qual o meliponicultor as conhece.
SPECIES = [
    ("Melipona scutellaris", "uruçu-nordestina"),
    ("Melipona subnitida", "jandaíra"),
    ("Scaptotrigona depilis", "canudo"),
]


@bp.route("/")
def index():
    # Quem ja esta autenticado quer o painel, nao a apresentacao do projeto.
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    with session_scope() as session:
        stats = {
            "hives": session.scalar(select(func.count()).select_from(Hive)) or 0,
            "apiaries": session.scalar(select(func.count()).select_from(Apiary)) or 0,
            "measurements": session.scalar(select(func.count()).select_from(Measurement)) or 0,
            "nodes": session.scalar(select(func.count()).select_from(Node)) or 0,
        }

    return render_template("public/index.html", stats=stats, species=SPECIES)
