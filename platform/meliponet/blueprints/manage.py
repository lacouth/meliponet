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
from meliponet.db import sessao_do_request
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


def _texto(campo: str) -> str | None:
    """Le um campo de texto do formulario: vazio vira ``None``, nao string vazia.

    A diferenca importa no banco. String vazia e um valor gravado -- "o municipio e a
    palavra vazia" -- enquanto ``None`` e a ausencia, que e o que um campo deixado em
    branco significa de verdade.
    """
    valor = (request.form.get(campo) or "").strip()
    return valor or None


def _decimal(campo: str) -> float | None:
    """Le um campo numerico do formulario. Vazio ou ilegivel vira ``None``."""
    valor = request.form.get(campo)
    if not valor or not valor.strip():
        return None
    try:
        return float(valor)
    except ValueError:
        return None


def _meliponario_no_escopo(session, apiary_id: int) -> Apiary:
    """Carrega o meliponario, exigindo que ele seja visivel ao usuario.

    Existe porque a checagem e repetida em toda rota que recebe um id -- pela URL ou
    pelo formulario -- e o modo de falha de esquece-la e o silencio: um id forjado
    criaria colmeia dentro do meliponario de outra organizacao, sem erro nenhum.
    """
    apiary = session.scalar(scope.apiaries_for(current_user).where(Apiary.id == apiary_id))
    if apiary is None:
        abort(403)
    return apiary


def _colmeia_no_escopo(session, hive_id: int) -> Hive:
    """Irma de ``_meliponario_no_escopo``, para as colmeias."""
    hive = session.scalar(scope.hives_for(current_user).where(Hive.id == hive_id))
    if hive is None:
        abort(403)
    return hive


def _no_gerenciavel(session, node_id: int) -> Node:
    """Carrega o no que o usuario pode vincular ou desvincular.

    Um no que nao existe e 404; um que existe mas nao e seu e 403. Um no ainda sem dono
    pode ser adotado por quem administra; um no de outra organizacao, so por quem
    administra todas -- a regra inteira mora em ``scope.can_manage_node``.
    """
    node = session.scalar(
        select(Node).options(selectinload(Node.assignments)).where(Node.id == node_id)
    )
    if node is None:
        abort(404)
    if not scope.can_manage_node(session, current_user, node.id):
        abort(403)
    return node


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


def _local_input(value: datetime | None) -> str:
    """Formata um instante UTC para preencher um ``datetime-local`` do formulario.

    Inverso de ``_parse_local``. Sem ele, abrir a tela de edicao mostraria o campo de
    data vazio e salvar apagaria a data que ja estava gravada.
    """
    if value is None:
        return ""
    return value.astimezone(ZoneInfo(DISPLAY_TIMEZONE)).strftime("%Y-%m-%dT%H:%M")


@bp.route("/")
@login_required
def index():
    session = sessao_do_request()

    # Os `selectinload` daqui sao otimizacao: sem eles, cada meliponario e cada no da
    # lista dispararia uma consulta propria -- o classico N+1.
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
    sessao_do_request().add(
        Apiary(
            organization_id=current_user.organization_id,
            name=request.form["nome"].strip(),
            municipality=_texto("municipio"),
            latitude=_decimal("latitude"),
            longitude=_decimal("longitude"),
        )
    )
    flash("Meliponário cadastrado.", "ok")
    return redirect(url_for("manage.index"))


@bp.route("/colmeia", methods=["POST"])
@login_required
def create_hive():
    _require_manager()
    session = sessao_do_request()
    apiary = _meliponario_no_escopo(session, int(request.form["meliponario_id"]))

    session.add(
        Hive(
            apiary_id=apiary.id,
            name=request.form["nome"].strip(),
            species=_texto("especie"),
            box_type=_texto("caixa"),
            # Em branco significa "agora", que e o caso comum; mas uma colmeia
            # cadastrada semanas depois de instalada precisa da data verdadeira, e
            # e ela que delimita a serie da colmeia.
            installed_at=_parse_local(request.form.get("instalado_em")) or utcnow(),
        )
    )
    flash("Colmeia cadastrada.", "ok")
    return redirect(url_for("manage.index"))


@bp.route("/meliponario/<int:apiary_id>/editar", methods=["GET", "POST"])
@login_required
def edit_apiary(apiary_id: int):
    """Corrige o cadastro de um meliponario.

    Um cadastro so criavel e um cadastro que envelhece errado: municipio digitado com
    erro, coordenada trocada de sinal, estacao do INMET descoberta depois. Nada disso
    justifica recriar o meliponario, o que orfanaria as colmeias e a serie inteira.
    """
    _require_manager()
    apiary = _meliponario_no_escopo(sessao_do_request(), apiary_id)

    if request.method == "POST":
        apiary.name = request.form["nome"].strip()
        apiary.municipality = _texto("municipio")
        apiary.latitude = _decimal("latitude")
        apiary.longitude = _decimal("longitude")
        apiary.inmet_station = _texto("estacao_inmet")
        apiary.notes = _texto("observacoes")
        flash("Meliponário atualizado.", "ok")
        return redirect(url_for("manage.index"))

    return render_template("manage/apiary_edit.html", apiary=apiary)


@bp.route("/colmeia/<int:hive_id>/editar", methods=["GET", "POST"])
@login_required
def edit_hive(hive_id: int):
    """Corrige o cadastro de uma colmeia.

    Inclui a data de instalacao, que ate aqui era carimbada como "agora" no cadastro e
    nao tinha como ser ajustada depois -- e e ela que diz a partir de quando a serie
    daquela colmeia comeca a valer.
    """
    _require_manager()
    hive = _colmeia_no_escopo(sessao_do_request(), hive_id)

    if request.method == "POST":
        hive.name = request.form["nome"].strip()
        hive.species = _texto("especie")
        hive.box_type = _texto("caixa")
        hive.installed_at = _parse_local(request.form.get("instalado_em"))
        hive.notes = _texto("observacoes")
        flash("Colmeia atualizada.", "ok")
        return redirect(url_for("manage.index"))

    return render_template(
        "manage/hive_edit.html",
        hive=hive,
        # O campo `datetime-local` do HTML tem formato proprio, e a conversao e da view:
        # o template escreve o que recebe, sem saber de fuso.
        instalado_em=_local_input(hive.installed_at),
        species=SPECIES,
    )


@bp.route("/no/<int:node_id>/vincular", methods=["GET", "POST"])
@login_required
def assign_node(node_id: int):
    _require_manager()
    session = sessao_do_request()
    node = _no_gerenciavel(session, node_id)

    if request.method == "POST":
        hive = _colmeia_no_escopo(session, int(request.form["colmeia_id"]))
        installed_at = _parse_local(request.form.get("instalado_em")) or utcnow()

        # Fecha o vínculo anterior antes de abrir o novo: dois vínculos abertos ao
        # mesmo tempo tornariam ambígua a colmeia de uma leitura.
        current = node.current_assignment
        if current is not None:
            current.removed_at = installed_at

        # O nó passa a pertencer à organização **da colmeia**, não à de quem clicou.
        # Carimbar o usuário logado fazia um administrador levar consigo o nó que
        # adotasse para a colmeia de outra organização: o dono legítimo deixava de
        # enxergar o próprio nó e não conseguia mais desvinculá-lo, sem erro na tela.
        node.organization_id = hive.apiary.organization_id
        session.add(
            NodeAssignment(
                node_id=node.id,
                hive_id=hive.id,
                installed_at=installed_at,
                sensor_placement=_texto("posicionamento"),
                protocol_notes=_texto("observacoes"),
            )
        )
        flash(f"Nó {node.node_id} vinculado a {hive.name}.", "ok")
        return redirect(url_for("manage.index"))

    hives = list(
        session.scalars(
            scope.hives_for(current_user).options(selectinload(Hive.apiary)).order_by(Hive.name)
        )
    )

    return render_template(
        "manage/assign.html",
        node_id=node_id,
        node_label=node.node_id,
        current_hive=node.current_assignment.hive.name if node.current_assignment else None,
        hives=hives,
        species=SPECIES,
    )


@bp.route("/no/<int:node_id>/desvincular", methods=["POST"])
@login_required
def unassign_node(node_id: int):
    _require_manager()
    node = _no_gerenciavel(sessao_do_request(), node_id)

    current = node.current_assignment
    if current is None:
        flash("Esse nó já está sem colmeia.", "erro")
    else:
        # Fecha o período em vez de apagar o vínculo: as leituras já gravadas continuam
        # apontando para a colmeia certa, e o histórico de instalação é parte do
        # protocolo documentado.
        current.removed_at = utcnow()
        flash(f"Nó {node.node_id} desvinculado.", "ok")

    return redirect(url_for("manage.index"))
