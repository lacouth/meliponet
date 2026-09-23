"""Comandos de linha de comando da plataforma.

Existe um problema de partida em toda aplicacao com login: a primeira conta. Sem ela
ninguem entra, e pela interface nao da para criar porque criar exige estar logado.
Estes comandos resolvem isso a partir do terminal do servidor -- que e o unico lugar
onde a permissao pode ser presumida.
"""

import getpass
import sys

import click
from flask import Flask
from sqlalchemy import select

from meliponet.banco import abrir_sessao
from meliponet.modelos import Organizacao, Perfil, Usuario


@click.command("criar-usuario")
@click.option("--email", required=True)
@click.option("--nome", required=True)
@click.option("--organizacao", required=True, help="criada se ainda não existir")
@click.option(
    "--perfil",
    type=click.Choice([perfil.value for perfil in Perfil]),
    default=Perfil.ADMIN.value,
    help="meliponicultor vê só a própria organização; pesquisador e admin veem tudo",
)
@click.option("--senha", default=None, help="se omitida, é pedida interativamente")
def criar_usuario(email: str, nome: str, organizacao: str, perfil: str, senha: str | None) -> None:
    """Cria um usuário, e a organização dele se preciso."""
    # Pedir a senha interativamente evita que ela fique no histórico do shell.
    senha_escolhida = senha or getpass.getpass("Senha: ")
    if len(senha_escolhida) < 8:
        click.echo("A senha precisa ter ao menos 8 caracteres.", err=True)
        sys.exit(1)

    email = email.strip().lower()

    with abrir_sessao() as session:
        if session.scalar(select(Usuario).where(Usuario.email == email)) is not None:
            click.echo(f"Já existe um usuário com o e-mail {email}.", err=True)
            sys.exit(1)

        organizacao_db = session.scalar(
            select(Organizacao).where(Organizacao.name == organizacao)
        )
        if organizacao_db is None:
            organizacao_db = Organizacao(name=organizacao)
            session.add(organizacao_db)
            session.flush()
            click.echo(f"Organização criada: {organizacao}")

        usuario = Usuario(
            organization_id=organizacao_db.id,
            email=email,
            name=nome,
            role=Perfil(perfil),
        )
        usuario.set_password(senha_escolhida)
        session.add(usuario)

    click.echo(f"Usuário {email} criado como {Perfil(perfil).label} em {organizacao}.")


@click.command("listar-usuarios")
def listar_usuarios() -> None:
    with abrir_sessao() as session:
        usuarios = list(session.scalars(select(Usuario).order_by(Usuario.email)))
        if not usuarios:
            click.echo("Nenhum usuário cadastrado. Use `flask criar-usuario`.")
            return
        for usuario in usuarios:
            status = "" if usuario.is_active else " (inativo)"
            click.echo(
                f"{usuario.email:34s} {usuario.role.value:16s} "
                f"{usuario.organization.name}{status}"
            )


def register(app: Flask) -> None:
    app.cli.add_command(criar_usuario)
    app.cli.add_command(listar_usuarios)
