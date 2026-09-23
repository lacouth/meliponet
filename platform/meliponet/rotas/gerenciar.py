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
from sqlalchemy.orm import Session, selectinload

from meliponet.banco import sessao_do_request
from meliponet.configuracao import FUSO_DE_EXIBICAO
from meliponet.modelos import Colmeia, Meliponario, No, Vinculo, agora_utc
from meliponet.servicos import escopo

bp = Blueprint("gerenciar", __name__, url_prefix="/gerenciar")

#: Especies-alvo da parceria, oferecidas no cadastro para padronizar a grafia -- nomes
#: cientificos digitados a mao divergem e inviabilizam agrupar series por especie.
ESPECIES = [
    "Melipona scutellaris",
    "Melipona subnitida",
    "Scaptotrigona depilis",
]


def _exigir_quem_administra() -> None:
    if not escopo.pode_gerenciar(current_user):
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
    valor = (request.form.get(campo) or "").strip()
    if not valor:
        return None
    try:
        return float(valor)
    except ValueError:
        return None


def _meliponario_no_escopo(session: Session, meliponario_id: int) -> Meliponario:
    """Carrega o meliponario, exigindo que ele seja visivel ao usuario.

    Existe porque a checagem e repetida em toda rota que recebe um id -- pela URL ou
    pelo formulario -- e o modo de falha de esquece-la e o silencio: um id forjado
    criaria colmeia dentro do meliponario de outra organizacao, sem erro nenhum.
    """
    meliponario = session.scalar(
        escopo.meliponarios_visiveis(current_user).where(Meliponario.id == meliponario_id)
    )
    if meliponario is None:
        abort(403)
    return meliponario


def _colmeia_no_escopo(session: Session, colmeia_id: int) -> Colmeia:
    """Irma de ``_meliponario_no_escopo``, para as colmeias."""
    colmeia = session.scalar(
        escopo.colmeias_visiveis(current_user).where(Colmeia.id == colmeia_id)
    )
    if colmeia is None:
        abort(403)
    return colmeia


def _no_gerenciavel(session: Session, no_id: int) -> No:
    """Carrega o no que o usuario pode vincular ou desvincular.

    Um no que nao existe e 404; um que existe mas nao e seu e 403. Um no ainda sem dono
    pode ser adotado por quem administra; um no de outra organizacao, so por quem
    administra todas -- a regra inteira mora em ``escopo.pode_gerenciar_no``.
    """
    no = session.scalar(
        select(No).options(selectinload(No.assignments)).where(No.id == no_id)
    )
    if no is None:
        abort(404)
    if not escopo.pode_gerenciar_no(session, current_user, no.id):
        abort(403)
    return no


def _ler_instante_local(valor: str | None) -> datetime | None:
    """Le um ``datetime-local`` do formulario como horario da Paraiba e devolve UTC.

    O campo HTML nao carrega fuso. Interpretar o valor como UTC deslocaria toda
    instalacao em tres horas, e a data de instalacao e o que delimita a que colmeia
    cada leitura pertence.
    """
    if not valor:
        return None
    ingenuo = datetime.fromisoformat(valor)
    return ingenuo.replace(tzinfo=ZoneInfo(FUSO_DE_EXIBICAO)).astimezone(UTC)


def _escrever_instante_local(valor: datetime | None) -> str:
    """Formata um instante UTC para preencher um ``datetime-local`` do formulario.

    Inverso de ``_ler_instante_local``. Sem ele, abrir a tela de edicao mostraria o
    campo de data vazio e salvar apagaria a data que ja estava gravada.
    """
    if valor is None:
        return ""
    return valor.astimezone(ZoneInfo(FUSO_DE_EXIBICAO)).strftime("%Y-%m-%dT%H:%M")


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
    # Nos que apareceram sozinhos na ingestao e ainda nao tem dono. So quem
    # administra os ve, porque so essa pessoa pode adota-los.
    pendentes = []
    if pode_gerenciar:
        pendentes = list(
            session.scalars(
                select(No)
                .options(selectinload(No.assignments))
                .where(No.organization_id.is_(None))
                .order_by(No.node_id)
            )
        )

    return render_template(
        "manage/index.html",
        meliponarios=meliponarios,
        nos=nos,
        pendentes=pendentes,
        especies=ESPECIES,
        pode_gerenciar=pode_gerenciar,
    )


@bp.route("/meliponario", methods=["POST"])
@login_required
def criar_meliponario():
    _exigir_quem_administra()
    sessao_do_request().add(
        Meliponario(
            organization_id=current_user.organization_id,
            name=request.form["nome"].strip(),
            municipality=_texto("municipio"),
            latitude=_decimal("latitude"),
            longitude=_decimal("longitude"),
        )
    )
    flash("Meliponário cadastrado.", "ok")
    return redirect(url_for("gerenciar.index"))


@bp.route("/colmeia", methods=["POST"])
@login_required
def criar_colmeia():
    _exigir_quem_administra()
    session = sessao_do_request()
    meliponario = _meliponario_no_escopo(session, int(request.form["meliponario_id"]))

    session.add(
        Colmeia(
            apiary_id=meliponario.id,
            name=request.form["nome"].strip(),
            species=_texto("especie"),
            box_type=_texto("caixa"),
            # Em branco significa "agora", que e o caso comum; mas uma colmeia
            # cadastrada semanas depois de instalada precisa da data verdadeira, e
            # e ela que delimita a serie da colmeia.
            installed_at=_ler_instante_local(request.form.get("instalado_em")) or agora_utc(),
        )
    )
    flash("Colmeia cadastrada.", "ok")
    return redirect(url_for("gerenciar.index"))


@bp.route("/meliponario/<int:meliponario_id>/editar", methods=["GET", "POST"])
@login_required
def editar_meliponario(meliponario_id: int):
    """Corrige o cadastro de um meliponario.

    Um cadastro so criavel e um cadastro que envelhece errado: municipio digitado com
    erro, coordenada trocada de sinal, estacao do INMET descoberta depois. Nada disso
    justifica recriar o meliponario, o que orfanaria as colmeias e a serie inteira.
    """
    _exigir_quem_administra()
    meliponario = _meliponario_no_escopo(sessao_do_request(), meliponario_id)

    if request.method == "POST":
        meliponario.name = request.form["nome"].strip()
        meliponario.municipality = _texto("municipio")
        meliponario.latitude = _decimal("latitude")
        meliponario.longitude = _decimal("longitude")
        meliponario.inmet_station = _texto("estacao_inmet")
        meliponario.notes = _texto("observacoes")
        flash("Meliponário atualizado.", "ok")
        return redirect(url_for("gerenciar.index"))

    return render_template("manage/apiary_edit.html", meliponario=meliponario)


@bp.route("/colmeia/<int:colmeia_id>/editar", methods=["GET", "POST"])
@login_required
def editar_colmeia(colmeia_id: int):
    """Corrige o cadastro de uma colmeia.

    Inclui a data de instalacao, que ate aqui era carimbada como "agora" no cadastro e
    nao tinha como ser ajustada depois -- e e ela que diz a partir de quando a serie
    daquela colmeia comeca a valer.
    """
    _exigir_quem_administra()
    colmeia = _colmeia_no_escopo(sessao_do_request(), colmeia_id)

    if request.method == "POST":
        colmeia.name = request.form["nome"].strip()
        colmeia.species = _texto("especie")
        colmeia.box_type = _texto("caixa")
        colmeia.installed_at = _ler_instante_local(request.form.get("instalado_em"))
        colmeia.notes = _texto("observacoes")
        flash("Colmeia atualizada.", "ok")
        return redirect(url_for("gerenciar.index"))

    return render_template(
        "manage/hive_edit.html",
        colmeia=colmeia,
        # O campo `datetime-local` do HTML tem formato proprio, e a conversao e da
        # rota: o template escreve o que recebe, sem saber de fuso.
        instalado_em=_escrever_instante_local(colmeia.installed_at),
        especies=ESPECIES,
    )


@bp.route("/no/<int:no_id>/vincular", methods=["GET", "POST"])
@login_required
def vincular_no(no_id: int):
    _exigir_quem_administra()
    session = sessao_do_request()
    no = _no_gerenciavel(session, no_id)

    if request.method == "POST":
        colmeia = _colmeia_no_escopo(session, int(request.form["colmeia_id"]))
        instalado_em = _ler_instante_local(request.form.get("instalado_em")) or agora_utc()

        # Fecha o vínculo anterior antes de abrir o novo: dois vínculos abertos ao
        # mesmo tempo tornariam ambígua a colmeia de uma leitura.
        vinculo_atual = no.vinculo_atual
        if vinculo_atual is not None:
            vinculo_atual.removed_at = instalado_em

        # O nó passa a pertencer à organização **da colmeia**, não à de quem clicou.
        # Carimbar o usuário logado fazia um administrador levar consigo o nó que
        # adotasse para a colmeia de outra organização: o dono legítimo deixava de
        # enxergar o próprio nó e não conseguia mais desvinculá-lo, sem erro na tela.
        no.organization_id = colmeia.apiary.organization_id
        session.add(
            Vinculo(
                node_id=no.id,
                hive_id=colmeia.id,
                installed_at=instalado_em,
                sensor_placement=_texto("posicionamento"),
                protocol_notes=_texto("observacoes"),
            )
        )
        flash(f"Nó {no.node_id} vinculado a {colmeia.name}.", "ok")
        return redirect(url_for("gerenciar.index"))

    colmeias = list(
        session.scalars(
            escopo.colmeias_visiveis(current_user)
            .options(selectinload(Colmeia.apiary))
            .order_by(Colmeia.name)
        )
    )

    return render_template(
        "manage/assign.html",
        no_id=no_id,
        no_label=no.node_id,
        colmeia_atual=no.vinculo_atual.hive.name if no.vinculo_atual else None,
        colmeias=colmeias,
        especies=ESPECIES,
    )


@bp.route("/no/<int:no_id>/desvincular", methods=["POST"])
@login_required
def desvincular_no(no_id: int):
    _exigir_quem_administra()
    no = _no_gerenciavel(sessao_do_request(), no_id)

    vinculo_atual = no.vinculo_atual
    if vinculo_atual is None:
        flash("Esse nó já está sem colmeia.", "erro")
    else:
        # Fecha o período em vez de apagar o vínculo: as leituras já gravadas continuam
        # apontando para a colmeia certa, e o histórico de instalação é parte do
        # protocolo documentado.
        vinculo_atual.removed_at = agora_utc()
        flash(f"Nó {no.node_id} desvinculado.", "ok")

    return redirect(url_for("gerenciar.index"))
