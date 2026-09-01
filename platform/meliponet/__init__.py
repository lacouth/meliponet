"""Plataforma web MelipoNet."""

from __future__ import annotations

from flask import Flask

from meliponet.config import DISPLAY_TIMEZONE, Config


def create_app(config: Config | None = None) -> Flask:
    """Fabrica da aplicacao.

    Sem estado global de configuracao: o app e montado a partir de um :class:`Config`
    explicito, o que permite aos testes criarem instancias isoladas com bancos
    proprios em vez de compartilharem um singleton.
    """
    from meliponet.blueprints.dashboard import bp as dashboard_bp
    from meliponet.db import create_all, init_engine

    config = config or Config.from_env()

    app = Flask(__name__)
    app.config["SECRET_KEY"] = config.secret_key
    app.config["MELIPONET"] = config
    app.config["DISPLAY_TIMEZONE"] = DISPLAY_TIMEZONE

    engine = init_engine(config.database_url)
    create_all(engine)

    app.register_blueprint(dashboard_bp)

    return app
