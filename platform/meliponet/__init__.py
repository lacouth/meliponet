"""Plataforma web MelipoNet."""

from __future__ import annotations

from flask import Flask
from flask_login import LoginManager

from meliponet.configuracao import FUSO_DE_EXIBICAO, Configuracao


def criar_app(configuracao: Configuracao | None = None) -> Flask:
    """Fabrica da aplicacao.

    Sem estado global de configuracao: o app e montado a partir de uma
    :class:`Configuracao` explicita, o que permite aos testes criarem instancias
    isoladas com bancos proprios em vez de compartilharem um singleton.
    """
    from meliponet.banco import (
        criar_tabelas,
        iniciar_banco,
        registrar_sessao_por_request,
        sessao_do_request,
    )
    from meliponet.modelos import Usuario
    from meliponet.rotas.api import bp as api_bp
    from meliponet.rotas.autenticacao import bp as autenticacao_bp
    from meliponet.rotas.gerenciar import bp as gerenciar_bp
    from meliponet.rotas.painel import bp as painel_bp
    from meliponet.rotas.publico import bp as publico_bp

    configuracao = configuracao or Configuracao.do_ambiente()

    app = Flask(__name__)
    app.config["SECRET_KEY"] = configuracao.secret_key
    app.config["MELIPONET"] = configuracao
    app.config["FUSO_DE_EXIBICAO"] = FUSO_DE_EXIBICAO

    engine = iniciar_banco(configuracao.database_url)
    criar_tabelas(engine)
    registrar_sessao_por_request(app)

    login_manager = LoginManager()
    login_manager.login_view = "autenticacao.entrar"
    login_manager.login_message = "Entre para acessar esta página."
    login_manager.login_message_category = "erro"
    login_manager.init_app(app)

    @login_manager.user_loader
    def carregar_usuario(usuario_id: str) -> Usuario | None:
        return sessao_do_request().get(Usuario, int(usuario_id))

    from meliponet import cli

    cli.register(app)

    app.register_blueprint(api_bp)
    app.register_blueprint(publico_bp)
    app.register_blueprint(autenticacao_bp)
    app.register_blueprint(painel_bp)
    app.register_blueprint(gerenciar_bp)

    return app
