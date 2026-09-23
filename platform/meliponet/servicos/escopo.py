"""Escopo de visibilidade por usuario: quem enxerga o que.

Todo acesso a dados de colmeia passa por aqui. A regra vive num lugar so porque o modo
de falha dela e o silencio: uma consulta que esquece o filtro nao quebra e nao levanta
erro -- ela apenas mostra a um meliponicultor as colmeias de outro.

Os tres perfis e a historia de quem contornou este modulo estao em
``docs/guia/03-a-plataforma.md``.
"""

from __future__ import annotations

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from meliponet.modelos import Colmeia, Meliponario, No, Perfil, Usuario


def meliponarios_visiveis(usuario: Usuario) -> Select[tuple[Meliponario]]:
    """Meliponarios visiveis ao usuario."""
    consulta = select(Meliponario)
    if not usuario.role.ve_tudo:
        consulta = consulta.where(Meliponario.organization_id == usuario.organization_id)
    return consulta


def colmeias_visiveis(usuario: Usuario) -> Select[tuple[Colmeia]]:
    """Colmeias visiveis ao usuario."""
    consulta = select(Colmeia).join(Meliponario, Colmeia.apiary_id == Meliponario.id)
    if not usuario.role.ve_tudo:
        consulta = consulta.where(Meliponario.organization_id == usuario.organization_id)
    return consulta


def nos_visiveis(usuario: Usuario) -> Select[tuple[No]]:
    """Nos visiveis ao usuario.

    Nos sem organizacao -- auto-cadastrados na primeira telemetria -- so aparecem para
    quem administra, que e quem pode vincula-los a uma colmeia.
    """
    consulta = select(No)
    if not usuario.role.ve_tudo:
        consulta = consulta.where(No.organization_id == usuario.organization_id)
    return consulta


def nos_gerenciaveis(usuario: Usuario) -> Select[tuple[No]]:
    """Nos que o usuario pode vincular ou desvincular.

    E ``nos_visiveis`` mais os nos ainda sem dono: adotar um no recem-aparecido e
    justamente a operacao que lhe da organizacao, entao exigir que ele ja pertenca a
    alguem tornaria a adocao impossivel.

    Existe aqui, e nao como um ``if`` na rota, pela razao do modulo inteiro: a
    comparacao escrita a mao la dentro nao acompanhou os perfis que veem tudo, e o
    administrador passou a receber 403 nos nos que a propria tela lhe mostrava.
    """
    consulta = select(No)
    if not usuario.role.ve_tudo:
        consulta = consulta.where(
            or_(
                No.organization_id == usuario.organization_id,
                No.organization_id.is_(None),
            )
        )
    return consulta


def pode_ver_colmeia(session: Session, usuario: Usuario, colmeia_id: int) -> bool:
    """Autorizacao de acesso a uma colmeia especifica.

    Usada nas rotas que recebem o id pela URL. Sem esta checagem, trocar o numero no
    endereco seria suficiente para ler a colmeia de outra organizacao.
    """
    return (
        session.scalar(colmeias_visiveis(usuario).where(Colmeia.id == colmeia_id).limit(1))
        is not None
    )


def pode_gerenciar_no(session: Session, usuario: Usuario, no_id: int) -> bool:
    """Irma de ``pode_ver_colmeia``, para as rotas que recebem o id do no pela URL."""
    return (
        session.scalar(nos_gerenciaveis(usuario).where(No.id == no_id).limit(1)) is not None
    )


def pode_gerenciar(usuario: Usuario) -> bool:
    """Se o usuario pode criar e editar cadastros.

    O meliponicultor administra os proprios meliponarios: e ele quem instala o no na
    caixa e sabe onde cada sensor ficou. O pesquisador tem visao ampla mas de leitura,
    para que uma analise nao altere por engano o cadastro de campo de outra pessoa.

    Esta funcao responde apenas *se* o usuario administra, nunca *o que* ele alcanca --
    isso e das consultas de escopo acima.
    """
    return usuario.role in (Perfil.MELIPONICULTOR, Perfil.ADMIN)
