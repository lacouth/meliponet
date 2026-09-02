"""Cadastro de meliponarios, colmeias e nos.

A tela mais importante daqui e a de vinculo no <-> colmeia: e nela que os metadados de
instalacao exigidos pelo Edital 17 sao registrados. Uma serie de temperatura sem saber
onde o sensor estava dentro da caixa nao e um dado cientifico reutilizavel, e o momento
de capturar isso e o da instalacao -- nao meses depois, de memoria.
"""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from meliponet.config import DISPLAY_TIMEZONE
from meliponet.db import session_scope
from meliponet.models import Apiary, Hive, Node, NodeAssignment, utcnow
from meliponet.services import scope

bp = Blueprint("manage", __name__, url_prefix="/gerenciar")

#: Especies-alvo da parceria, oferecidas no cadastro para padronizar a grafia -- nomes
#: cientificos digitados a mao divergem e inviabilizam agrupar series por especie.
SPECIES = [
    "Melipona scutellaris",
    "Melipona subnitida",
    "Scaptotrigona depilis",
]


def _require_manager() -> None:
    if not scope.can_manage(current_user):
        abort(403)


def _parse_local(value: str | None) -> datetime | None:
    """Le um ``datetime-local`` do formulario como horario da Paraiba e devolve UTC.

    O campo HTML nao carrega fuso. Interpretar o valor como UTC deslocaria toda
    instalacao em tres horas, e a data de instalacao e o que delimita a que colmeia
    cada leitura pertence.
    """
    if not value:
        return None
    naive = datetime.fromisoformat(value)
    return naive.replace(tzinfo=ZoneInfo(DISPLAY_TIMEZONE)).astimezone(UTC)


@bp.route("/")
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
        nodes = list(
            session.scalars(
                scope.nodes_for(current_user)
                .options(selectinload(Node.assignments).selectinload(NodeAssignment.hive))
                .order_by(Node.node_id)
            )
        )
        # Nos que apareceram sozinhos na ingestao e ainda nao tem dono. So quem
        # administra os ve, porque so essa pessoa pode adota-los.
        pending = (
            list(
                session.scalars(
                    select(Node)
                    .options(selectinload(Node.assignments))
                    .where(Node.organization_id.is_(None))
                    .order_by(Node.node_id)
                )
            )
            if scope.can_manage(current_user)
            else []
        )

    return render_template(
        "manage/index.html",
        apiaries=apiaries,
        nodes=nodes,
        pending=pending,
        species=SPECIES,
        pode_gerenciar=scope.can_manage(current_user),
    )


@bp.route("/meliponario", methods=["POST"])
@login_required
def create_apiary():
    _require_manager()
    with session_scope() as session:
        session.add(
            Apiary(
                organization_id=current_user.organization_id,
                name=request.form["nome"].strip(),
                municipality=(request.form.get("municipio") or "").strip() or None,
                latitude=_float_or_none(request.form.get("latitude")),
                longitude=_float_or_none(request.form.get("longitude")),
            )
        )
    flash("Meliponário cadastrado.", "ok")
    return redirect(url_for("manage.index"))


@bp.route("/colmeia", methods=["POST"])
@login_required
def create_hive():
    _require_manager()
    apiary_id = int(request.form["meliponario_id"])

    with session_scope() as session:
        # Confere que o meliponário é visível ao usuário antes de pendurar a colmeia
        # nele: sem isso, um id forjado no formulário criaria uma colmeia dentro do
        # meliponário de outra organização.
        apiary = session.scalar(scope.apiaries_for(current_user).where(Apiary.id == apiary_id))
        if apiary is None:
            abort(403)

        session.add(
            Hive(
                apiary_id=apiary.id,
                name=request.form["nome"].strip(),
                species=(request.form.get("especie") or "").strip() or None,
                box_type=(request.form.get("caixa") or "").strip() or None,
                installed_at=utcnow(),
            )
        )
    flash("Colmeia cadastrada.", "ok")
    return redirect(url_for("manage.index"))


@bp.route("/no/<int:node_id>/vincular", methods=["GET", "POST"])
@login_required
def assign_node(node_id: int):
    _require_manager()

    with session_scope() as session:
        node = session.scalar(
            select(Node).options(selectinload(Node.assignments)).where(Node.id == node_id)
        )
        if node is None:
            abort(404)
        # Um nó ainda sem dono pode ser adotado por quem administra; um nó de outra
        # organização, só por quem administra todas.
        if not scope.can_manage_node(session, current_user, node.id):
            abort(403)

        if request.method == "POST":
            hive_id = int(request.form["colmeia_id"])
            hive = session.scalar(scope.hives_for(current_user).where(Hive.id == hive_id))
            if hive is None:
                abort(403)

            installed_at = _parse_local(request.form.get("instalado_em")) or utcnow()

            # Fecha o vínculo anterior antes de abrir o novo: dois vínculos abertos ao
            # mesmo tempo tornariam ambígua a colmeia de uma leitura.
            current = node.current_assignment
            if current is not None:
                current.removed_at = installed_at

            # O nó passa a pertencer à organização **da colmeia**, não à de quem
            # clicou. Carimbar o usuário logado fazia um administrador levar consigo o
            # nó que adotasse para a colmeia de outra organização: o dono legítimo
            # deixava de enxergar o próprio nó e não conseguia mais desvinculá-lo, sem
            # erro nenhum na tela.
            node.organization_id = hive.apiary.organization_id
            session.add(
                NodeAssignment(
                    node_id=node.id,
                    hive_id=hive.id,
                    installed_at=installed_at,
                    sensor_placement=(request.form.get("posicionamento") or "").strip() or None,
                    protocol_notes=(request.form.get("observacoes") or "").strip() or None,
                )
            )
            flash(f"Nó {node.node_id} vinculado a {hive.name}.", "ok")
            return redirect(url_for("manage.index"))

        # Carrega o meliponário junto: o template mostra "Colmeia (Meliponário)" e
        # renderiza depois que a sessão fechou.
        hives = list(
            session.scalars(
                scope.hives_for(current_user)
                .options(selectinload(Hive.apiary))
                .order_by(Hive.name)
            )
        )
        node_label = node.node_id
        current_hive = node.current_assignment.hive.name if node.current_assignment else None

    return render_template(
        "manage/assign.html",
        node_id=node_id,
        node_label=node_label,
        current_hive=current_hive,
        hives=hives,
        species=SPECIES,
    )


@bp.route("/no/<int:node_id>/desvincular", methods=["POST"])
@login_required
def unassign_node(node_id: int):
    _require_manager()
    with session_scope() as session:
        node = session.scalar(
            select(Node).options(selectinload(Node.assignments)).where(Node.id == node_id)
        )
        if node is None:
            abort(404)
        if not scope.can_manage_node(session, current_user, node.id):
            abort(403)

        current = node.current_assignment
        if current is None:
            flash("Esse nó já está sem colmeia.", "erro")
        else:
            # Fecha o período em vez de apagar o vínculo: as leituras já gravadas
            # continuam apontando para a colmeia certa, e o histórico de instalação é
            # parte do protocolo documentado.
            current.removed_at = utcnow()
            flash(f"Nó {node.node_id} desvinculado.", "ok")

    return redirect(url_for("manage.index"))


def _float_or_none(value: str | None) -> float | None:
    if not value or not value.strip():
        return None
    try:
        return float(value)
    except ValueError:
        return None
