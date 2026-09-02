"""Plataforma web MelipoNet."""

from __future__ import annotations

from flask import Flask
from flask_login import LoginManager

from meliponet.config import DISPLAY_TIMEZONE, Config


def create_app(config: Config | None = None) -> Flask:
    """Fabrica da aplicacao.

    Sem estado global de configuracao: o app e montado a partir de um :class:`Config`
    explicito, o que permite aos testes criarem instancias isoladas com bancos proprios
    em vez de compartilharem um singleton.
    """
    from meliponet.blueprints.auth import bp as auth_bp
    from meliponet.blueprints.dashboard import bp as dashboard_bp
    from meliponet.blueprints.manage import bp as manage_bp
    from meliponet.blueprints.public import bp as public_bp
    from meliponet.db import create_all, init_engine, session_scope
    from meliponet.models import User

    config = config or Config.from_env()

    app = Flask(__name__)
    app.config["SECRET_KEY"] = config.secret_key
    app.config["MELIPONET"] = config
    app.config["DISPLAY_TIMEZONE"] = DISPLAY_TIMEZONE

    engine = init_engine(config.database_url)
    create_all(engine)

    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Entre para acessar esta página."
    login_manager.login_message_category = "erro"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str) -> User | None:
        # A sessao do request e fechada aqui; `expire_on_commit=False` mantem os
        # atributos ja carregados acessiveis nos templates depois disso.
        with session_scope() as session:
            user = session.get(User, int(user_id))
            if user is not None:
                # A organizacao e lida em quase toda pagina; carregar aqui evita um
                # DetachedInstanceError no template.
                _ = user.organization.name
            return user

    from meliponet import cli

    cli.register(app)

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(manage_bp)

    return app
