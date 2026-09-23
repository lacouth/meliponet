"""Painel: a visao que o meliponicultor abre para saber como esta a colmeia."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Blueprint, abort, current_app, render_template, request
from flask_login import current_user, login_required
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from meliponet.banco import sessao_do_request
from meliponet.modelos import Colmeia, Medicao, Meliponario, Recusa
from meliponet.servicos import escopo
from meliponet.servicos import serie as servico_de_serie

bp = Blueprint("painel", __name__)


def _fuso_de_exibicao() -> ZoneInfo:
    return ZoneInfo(current_app.config["FUSO_DE_EXIBICAO"])


@bp.app_template_filter("hora_local")
def hora_local(valor: datetime | None) -> str:
    """Converte para o fuso de exibicao.

    Os dados sao gravados em UTC e so aqui viram horario da Paraiba. Fazer a conversao
    na apresentacao, e nao na gravacao, e o que impede que uma mudanca de fuso corrompa
    uma serie ja coletada.
    """
    if valor is None:
        return "—"
    return valor.astimezone(_fuso_de_exibicao()).strftime("%d/%m/%Y %H:%M")


@bp.app_template_filter("numero")
def numero(valor: float | None, casas: int = 1, sufixo: str = "") -> str:
    if valor is None:
        return "—"
    return f"{valor:.{casas}f}{sufixo}"


@bp.route("/colmeias")
@login_required
def index():
    session = sessao_do_request()

    # Este `selectinload` e otimizacao de verdade, e nao defesa contra sessao fechada:
    # sem ele, cada meliponario da lista dispararia uma consulta propria para buscar as
    # colmeias -- o classico N+1.
    meliponarios = list(
        session.scalars(
            escopo.meliponarios_visiveis(current_user)
            .options(selectinload(Meliponario.hives))
            .order_by(Meliponario.name)
        )
    )
    visao_geral = [
        {
            "meliponario": meliponario,
            "colmeia": colmeia,
            "ultima": servico_de_serie.ultima_leitura(session, colmeia.id),
        }
        for meliponario in meliponarios
        for colmeia in meliponario.hives
    ]

    colmeia_ids = [linha["colmeia"].id for linha in visao_geral]
    total_de_medicoes = (
        session.scalar(
            select(func.count()).select_from(Medicao).where(Medicao.hive_id.in_(colmeia_ids))
        )
        or 0
    )
    # Recusas nao pertencem a colmeia nenhuma (a mensagem sequer foi decodificada),
    # entao so quem tem visao ampla as ve.
    recusas = []
    if current_user.role.ve_tudo:
        recusas = list(
            session.scalars(select(Recusa).order_by(Recusa.received_at.desc()).limit(5))
        )

    return render_template(
        "index.html",
        visao_geral=visao_geral,
        total_de_medicoes=total_de_medicoes,
        recusas=recusas,
    )


def _colmeia_visivel(session: Session, colmeia_id: int) -> Colmeia:
    """Carrega a colmeia visivel ao usuario.

    O escopo por usuario vem de ``escopo.colmeias_visiveis``, e nao de um
    ``select(Colmeia)`` cru: sem isso, trocar o numero na URL leria a colmeia de outra
    organizacao.

    Colmeia inexistente e colmeia de outra organizacao devolvem o mesmo 404: distinguir
    as duas revelaria quais ids existem na plataforma.
    """
    colmeia = session.scalar(
        escopo.colmeias_visiveis(current_user).where(Colmeia.id == colmeia_id)
    )
    if colmeia is None:
        abort(404)
    return colmeia


def _janela_pedida() -> str:
    """A janela vinda da URL, ou a padrao quando ela nao existe.

    Uma janela desconhecida cai na padrao em vez de virar erro: o parametro vem da URL,
    e um endereco digitado a mao nao deve derrubar a tela.
    """
    janela = request.args.get("janela", servico_de_serie.JANELA_PADRAO)
    if janela not in servico_de_serie.JANELAS:
        return servico_de_serie.JANELA_PADRAO
    return janela


@bp.route("/colmeia/<int:colmeia_id>")
@login_required
def detalhe_da_colmeia(colmeia_id: int):
    janela = _janela_pedida()
    session = sessao_do_request()
    contexto = _contexto_da_colmeia(session, _colmeia_visivel(session, colmeia_id), janela)

    return render_template("hive.html", **contexto)


@bp.route("/colmeia/<int:colmeia_id>/painel")
@login_required
def fragmento_da_colmeia(colmeia_id: int):
    """Fragmento recarregado pelo HTMX.

    O painel atualiza por polling de um fragmento, e nao por WebSocket ou SSE: com
    amostragem de 5 minutos, a conexao persistente nao se paga e e fragil justamente
    onde o sistema precisa funcionar, que e a conectividade rural.
    """
    janela = _janela_pedida()
    session = sessao_do_request()
    contexto = _contexto_da_colmeia(session, _colmeia_visivel(session, colmeia_id), janela)

    return render_template("_panel.html", **contexto)


def _diferencial_termico(pontos: list[servico_de_serie.Ponto]) -> list[float | None]:
    """Quanto a colmeia esta mais quente que o lado de fora, ponto a ponto.

    Um ponto que nao tem as duas temperaturas vira ``None``, e nao zero: zero seria
    lido no grafico como "dentro e fora na mesma temperatura", que e uma afirmacao que
    a leitura nao fez.
    """
    diferencas: list[float | None] = []
    for ponto in pontos:
        dentro = ponto.values.get("temp_in_c")
        fora = ponto.values.get("temp_out_c")
        if dentro is None or fora is None:
            diferencas.append(None)
        else:
            diferencas.append(round(dentro - fora, 2))
    return diferencas


def _contexto_da_colmeia(session: Session, colmeia: Colmeia, janela: str) -> dict:
    pontos = servico_de_serie.serie(session, colmeia.id, janela)
    fuso = _fuso_de_exibicao()

    grafico = {
        "labels": [p.time.astimezone(fuso).strftime("%d/%m %H:%M") for p in pontos],
        "series": {
            coluna: [p.values.get(coluna) for p in pontos]
            for coluna in servico_de_serie.COLUNAS_DE_METRICA
        },
        "thermal_differential": _diferencial_termico(pontos),
    }

    return {
        "colmeia": colmeia,
        "janela": janela,
        "janelas": servico_de_serie.JANELAS,
        "ultima": servico_de_serie.ultima_leitura(session, colmeia.id),
        "completude": servico_de_serie.completude(session, colmeia.id, janela),
        "grafico": grafico,
        "quantos_pontos": len(pontos),
    }
