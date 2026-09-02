"""Dashboard: a visao que o meliponicultor abre para saber como esta a colmeia."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Blueprint, abort, current_app, render_template, request
from flask_login import current_user, login_required
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from meliponet.db import session_scope
from meliponet.models import Apiary, Hive, IngestReject, Measurement
from meliponet.services import scope
from meliponet.services import series as series_service

bp = Blueprint("dashboard", __name__)


def _display_tz() -> ZoneInfo:
    return ZoneInfo(current_app.config["DISPLAY_TIMEZONE"])


@bp.app_template_filter("localtime")
def localtime(value: datetime | None) -> str:
    """Converte para o fuso de exibicao.

    Os dados sao gravados em UTC e so aqui viram horario da Paraiba. Fazer a conversao
    na apresentacao, e nao na gravacao, e o que impede que uma mudanca de fuso corrompa
    uma serie ja coletada.
    """
    if value is None:
        return "—"
    return value.astimezone(_display_tz()).strftime("%d/%m/%Y %H:%M")


@bp.app_template_filter("num")
def num(value: float | None, digits: int = 1, suffix: str = "") -> str:
    if value is None:
        return "—"
    return f"{value:.{digits}f}{suffix}"


@bp.route("/colmeias")
@login_required
def index():
    with session_scope() as session:
        apiaries = list(
            session.scalars(
                scope.apiaries_for(current_user)
                .options(selectinload(Apiary.hives))
                .order_by(Apiary.name)
            )
        )
        overview = [
            {
                "apiary": apiary,
                "hive": hive,
                "latest": series_service.latest(session, hive.id),
            }
            for apiary in apiaries
            for hive in apiary.hives
        ]

        hive_ids = [row["hive"].id for row in overview]
        total_measurements = (
            session.scalar(
                select(func.count())
                .select_from(Measurement)
                .where(Measurement.hive_id.in_(hive_ids))
            )
            or 0
        )
        # Recusas nao pertencem a colmeia nenhuma (a mensagem sequer foi decodificada),
        # entao so quem tem visao ampla as ve.
        rejects = (
            list(
                session.scalars(
                    select(IngestReject).order_by(IngestReject.received_at.desc()).limit(5)
                )
            )
            if current_user.role.sees_everything
            else []
        )

    return render_template(
        "index.html",
        overview=overview,
        total_measurements=total_measurements,
        rejects=rejects,
    )


def _load_hive(session: Session, hive_id: int) -> Hive:
    """Carrega a colmeia visivel ao usuario, com o meliponario junto.

    Duas coisas ao mesmo tempo, de proposito. O escopo por usuario vem de
    ``scope.hives_for``, e nao de um ``select(Hive)`` cru: sem isso, trocar o numero na
    URL leria a colmeia de outra organizacao. E o eager load do meliponario nao e
    otimizacao -- os templates renderizam depois que a sessao fechou, e um lazy load
    nesse ponto levanta DetachedInstanceError.

    Colmeia inexistente e colmeia de outra organizacao devolvem o mesmo 404: distinguir
    as duas revelaria quais ids existem na plataforma.
    """
    hive = session.scalar(
        scope.hives_for(current_user).options(joinedload(Hive.apiary)).where(Hive.id == hive_id)
    )
    if hive is None:
        abort(404)
    return hive


@bp.route("/colmeia/<int:hive_id>")
@login_required
def hive_detail(hive_id: int):
    window = request.args.get("janela", series_service.DEFAULT_WINDOW)
    if window not in series_service.WINDOWS:
        window = series_service.DEFAULT_WINDOW

    with session_scope() as session:
        context = _hive_context(session, _load_hive(session, hive_id), window)

    return render_template("hive.html", **context)


@bp.route("/colmeia/<int:hive_id>/painel")
@login_required
def hive_panel(hive_id: int):
    """Fragmento recarregado pelo HTMX.

    O dashboard atualiza por polling de um fragmento, e nao por WebSocket ou SSE: com
    amostragem de 5 minutos, a conexao persistente nao se paga e e fragil justamente
    onde o sistema precisa funcionar, que e a conectividade rural.
    """
    window = request.args.get("janela", series_service.DEFAULT_WINDOW)
    if window not in series_service.WINDOWS:
        window = series_service.DEFAULT_WINDOW

    with session_scope() as session:
        context = _hive_context(session, _load_hive(session, hive_id), window)

    return render_template("_panel.html", **context)


def _hive_context(session: Session, hive: Hive, window: str) -> dict:
    points = series_service.series(session, hive.id, window)
    tz = _display_tz()

    return {
        "hive": hive,
        "window": window,
        "windows": series_service.WINDOWS,
        "latest": series_service.latest(session, hive.id),
        "completeness": series_service.completeness(session, hive.id, window),
        "chart": {
            "labels": [p.time.astimezone(tz).strftime("%d/%m %H:%M") for p in points],
            "series": {
                column: [p.values.get(column) for p in points]
                for column in series_service.METRIC_COLUMNS
            },
            "thermal_differential": [
                None
                if p.values.get("temp_in_c") is None or p.values.get("temp_out_c") is None
                else round(p.values["temp_in_c"] - p.values["temp_out_c"], 2)
                for p in points
            ],
        },
        "point_count": len(points),
    }
