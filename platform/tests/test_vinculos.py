"""Testes das regras de vinculo no <-> colmeia, sem servidor web.

Complementam ``test_web.py``. La se confere que a rota aplica a permissao; aqui, que a
regra em si esta certa -- e sem HTTP, cada teste diz exatamente qual regra quebrou.
"""

from datetime import UTC, datetime, timedelta

from meliponet.banco import abrir_sessao
from meliponet.modelos import Colmeia, No, Vinculo
from meliponet.servicos import vinculos
from sqlalchemy import select


def _vinculos_do_no(session, no_pk: int) -> list[Vinculo]:
    return list(
        session.scalars(
            select(Vinculo).where(Vinculo.node_id == no_pk).order_by(Vinculo.installed_at)
        )
    )


def test_vincular_fecha_o_anterior_no_instante_do_novo(cenario) -> None:
    """Dois vinculos abertos ao mesmo tempo tornariam ambigua a colmeia de uma leitura."""
    agora = datetime.now(UTC).replace(microsecond=0)

    with abrir_sessao() as session:
        no = session.get(No, cenario.no_pk)
        nova = Colmeia(apiary_id=cenario.meliponario_id, name="Colmeia 02")
        session.add(nova)
        session.flush()
        vinculos.vincular(session, no, nova, agora, posicionamento="no teto")

    with abrir_sessao() as session:
        antigo, novo = _vinculos_do_no(session, cenario.no_pk)

    assert antigo.hive_id == cenario.colmeia_id
    assert antigo.removed_at == agora
    assert novo.removed_at is None
    assert novo.installed_at == agora
    assert novo.sensor_placement == "no teto"


def test_no_adotado_fica_com_a_organizacao_da_colmeia(cenario) -> None:
    """Nao com a de quem clicou: e a regra que ja nos custou um no sumido da tela."""
    with abrir_sessao() as session:
        orfao = No(node_id="FFFFAA01")
        session.add(orfao)
        session.flush()
        colmeia_alheia = session.get(Colmeia, cenario.outra_colmeia_id)
        vinculos.vincular(session, orfao, colmeia_alheia, datetime.now(UTC))
        orfao_pk = orfao.id

    with abrir_sessao() as session:
        assert session.get(No, orfao_pk).organization_id == cenario.outra_organizacao_id


def test_desvincular_fecha_o_periodo_sem_apagar(cenario) -> None:
    """As leituras ja gravadas continuam apontando para a colmeia em que o no estava."""
    with abrir_sessao() as session:
        assert vinculos.desvincular(session.get(No, cenario.no_pk)) is True

    with abrir_sessao() as session:
        (vinculo,) = _vinculos_do_no(session, cenario.no_pk)

    assert vinculo.removed_at is not None


def test_desvincular_no_solto_nao_faz_nada(cenario) -> None:
    with abrir_sessao() as session:
        orfao = No(node_id="FFFFAA02")
        session.add(orfao)
        session.flush()
        assert vinculos.desvincular(orfao) is False
        assert _vinculos_do_no(session, orfao.id) == []


def test_nos_pendentes_sao_so_os_sem_dono(cenario) -> None:
    with abrir_sessao() as session:
        session.add(No(node_id="FFFFAA03"))

    with abrir_sessao() as session:
        pendentes = [no.node_id for no in vinculos.nos_pendentes(session)]

    assert pendentes == ["FFFFAA03"]
    assert cenario.node_id not in pendentes


def test_vincular_no_passado_respeita_a_data_informada(cenario) -> None:
    """A data vem do formulario: uma instalacao registrada dias depois nao e 'agora'."""
    ontem = (datetime.now(UTC) - timedelta(days=1)).replace(microsecond=0)

    with abrir_sessao() as session:
        no = session.get(No, cenario.no_pk)
        colmeia = session.get(Colmeia, cenario.colmeia_id)
        vinculos.vincular(session, no, colmeia, ontem)

    with abrir_sessao() as session:
        novo = _vinculos_do_no(session, cenario.no_pk)[-1]

    assert novo.installed_at == ontem
