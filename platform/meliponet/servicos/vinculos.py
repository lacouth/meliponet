"""Vinculo no <-> colmeia: as regras de instalar e retirar um no.

As regras moram aqui, e nao na rota, para poderem ser testadas sem servidor web e
chamadas por quem nao e uma tela -- um script de importacao, um comando de terminal.
A rota so le o formulario, confere a permissao e chama estas funcoes.

O porque de o vinculo ser historico, e nao um campo do no, esta em
``docs/guia/03-a-plataforma.md``.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from meliponet.modelos import Colmeia, No, Vinculo, agora_utc


def vincular(
    session: Session,
    no: No,
    colmeia: Colmeia,
    instalado_em: datetime,
    posicionamento: str | None = None,
    observacoes: str | None = None,
) -> Vinculo:
    """Instala ``no`` em ``colmeia`` a partir de ``instalado_em``.

    Duas regras, e as duas ja nos custaram defeito:

    * O vinculo anterior e **fechado** no mesmo instante em que o novo abre. Dois
      vinculos abertos ao mesmo tempo tornariam ambigua a colmeia de uma leitura.
    * O no passa a pertencer a organizacao **da colmeia**, nao a de quem clicou.
      Carimbar o usuario logado fazia um administrador levar consigo o no que
      adotasse para a colmeia de outra organizacao: o dono legitimo deixava de
      enxergar o proprio no, sem erro nenhum na tela.
    """
    vinculo_atual = no.vinculo_atual
    if vinculo_atual is not None:
        vinculo_atual.removed_at = instalado_em

    no.organization_id = colmeia.apiary.organization_id

    novo = Vinculo(
        node_id=no.id,
        hive_id=colmeia.id,
        installed_at=instalado_em,
        sensor_placement=posicionamento,
        protocol_notes=observacoes,
    )
    session.add(novo)
    return novo


def desvincular(no: No) -> bool:
    """Retira ``no`` da colmeia em que ele esta. Devolve ``False`` se ele ja estava solto.

    Fecha o periodo em vez de apagar o vinculo: as leituras ja gravadas continuam
    apontando para a colmeia certa, e o historico de instalacao e parte do protocolo
    documentado.
    """
    vinculo_atual = no.vinculo_atual
    if vinculo_atual is None:
        return False
    vinculo_atual.removed_at = agora_utc()
    return True


def nos_pendentes(session: Session) -> list[No]:
    """Nos que apareceram sozinhos na ingestao e ainda nao tem dono.

    Quem decide se o usuario pode ve-los e a rota, com ``escopo.pode_gerenciar``: esta
    funcao so responde quais sao.
    """
    return list(
        session.scalars(
            select(No)
            .options(selectinload(No.assignments))
            .where(No.organization_id.is_(None))
            .order_by(No.node_id)
        )
    )
