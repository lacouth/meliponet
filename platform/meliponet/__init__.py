"""Plataforma web MelipoNet."""

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
    from meliponet.rotas import (
        api,
        autenticacao,
        cadastros,
        colmeias,
        meliponarios,
        nos,
        painel,
        publico,
    )

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

    # Cada arquivo de `rotas/` e um grupo de telas (um "blueprint"), e so passa a
    # responder depois de registrado aqui.
    app.register_blueprint(api.bp)
    app.register_blueprint(publico.bp)
    app.register_blueprint(autenticacao.bp)
    app.register_blueprint(painel.bp)
    app.register_blueprint(cadastros.bp)
    app.register_blueprint(meliponarios.bp)
    app.register_blueprint(colmeias.bp)
    app.register_blueprint(nos.bp)

    return app
