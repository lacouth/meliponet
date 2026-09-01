"""Comandos de linha de comando da plataforma.

Existe um problema de partida em toda aplicacao com login: a primeira conta. Sem ela
ninguem entra, e pela interface nao da para criar porque criar exige estar logado.
Estes comandos resolvem isso a partir do terminal do servidor -- que e o unico lugar
onde a permissao pode ser presumida.
"""

from __future__ import annotations

import getpass
import sys

import click
from flask import Flask
from sqlalchemy import select

from meliponet.db import session_scope
from meliponet.models import Organization, Role, User


@click.command("criar-usuario")
@click.option("--email", required=True)
@click.option("--nome", required=True)
@click.option("--organizacao", required=True, help="criada se ainda não existir")
@click.option(
    "--perfil",
    type=click.Choice([role.value for role in Role]),
    default=Role.ADMIN.value,
    help="meliponicultor vê só a própria organização; pesquisador e admin veem tudo",
)
@click.option("--senha", default=None, help="se omitida, é pedida interativamente")
def create_user(email: str, nome: str, organizacao: str, perfil: str, senha: str | None) -> None:
    """Cria um usuário, e a organização dele se preciso."""
    # Pedir a senha interativamente evita que ela fique no histórico do shell.
    password = senha or getpass.getpass("Senha: ")
    if len(password) < 8:
        click.echo("A senha precisa ter ao menos 8 caracteres.", err=True)
        sys.exit(1)

    email = email.strip().lower()

    with session_scope() as session:
        if session.scalar(select(User).where(User.email == email)) is not None:
            click.echo(f"Já existe um usuário com o e-mail {email}.", err=True)
            sys.exit(1)

        organization = session.scalar(select(Organization).where(Organization.name == organizacao))
        if organization is None:
            organization = Organization(name=organizacao)
            session.add(organization)
            session.flush()
            click.echo(f"Organização criada: {organizacao}")

        user = User(
            organization_id=organization.id,
            email=email,
            name=nome,
            role=Role(perfil),
        )
        user.set_password(password)
        session.add(user)

    click.echo(f"Usuário {email} criado como {Role(perfil).label} em {organizacao}.")


@click.command("listar-usuarios")
def list_users() -> None:
    with session_scope() as session:
        users = list(session.scalars(select(User).order_by(User.email)))
        if not users:
            click.echo("Nenhum usuário cadastrado. Use `flask criar-usuario`.")
            return
        for user in users:
            status = "" if user.is_active else " (inativo)"
            click.echo(f"{user.email:34s} {user.role.value:16s} {user.organization.name}{status}")


def register(app: Flask) -> None:
    app.cli.add_command(create_user)
    app.cli.add_command(list_users)
