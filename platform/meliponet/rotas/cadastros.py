"""A tela de cadastros: meliponarios, colmeias e nos numa pagina so.

So mostra. Criar, editar e vincular moram cada um no arquivo do seu assunto --
``meliponarios.py``, ``colmeias.py`` e ``nos.py`` --, todos sob o mesmo endereco
``/gerenciar/``.
"""

from flask import Blueprint, render_template
from flask_login import current_user, login_required
from sqlalchemy.orm import selectinload

from meliponet.banco import sessao_do_request
from meliponet.configuracao import NOMES_CIENTIFICOS
from meliponet.modelos import Meliponario, No, Vinculo
from meliponet.servicos import escopo, vinculos

bp = Blueprint("cadastros", __name__, url_prefix="/gerenciar")


@bp.route("/")
@login_required
def index():
    session = sessao_do_request()
    pode_gerenciar = escopo.pode_gerenciar(current_user)

    # Os `selectinload` daqui sao otimizacao: sem eles, cada meliponario e cada no da
    # lista dispararia uma consulta propria -- o classico N+1.
    meliponarios = list(
        session.scalars(
            escopo.meliponarios_visiveis(current_user)
            .options(selectinload(Meliponario.hives))
            .order_by(Meliponario.name)
        )
    )
    nos = list(
        session.scalars(
            escopo.nos_visiveis(current_user)
            .options(selectinload(No.assignments).selectinload(Vinculo.hive))
            .order_by(No.node_id)
        )
    )

    # Nos que apareceram sozinhos na ingestao e ainda nao tem dono. So quem administra
    # os ve, porque so essa pessoa pode adota-los.
    pendentes = []
    if pode_gerenciar:
        pendentes = vinculos.nos_pendentes(session)

    return render_template(
        "manage/index.html",
        meliponarios=meliponarios,
        nos=nos,
        pendentes=pendentes,
        especies=NOMES_CIENTIFICOS,
        pode_gerenciar=pode_gerenciar,
    )
