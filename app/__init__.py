from flask import Flask
from .config import get_config
from .extensions import db, login_manager, migrate, csrf, limiter


def create_app(config_class=None):
    app = Flask(__name__, instance_relative_config=True)

    if config_class is None:
        config_class = get_config()
    app.config.from_object(config_class)

    # Inicializa extensões
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    limiter.init_app(app)

    # Registra blueprints
    from .blueprints.auth import auth_bp
    from .blueprints.director import director_bp
    from .blueprints.teacher import teacher_bp
    from .blueprints.student import student_bp
    from .blueprints.parent import parent_bp
    from .blueprints.reports import reports_bp
    from .blueprints.api import api_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(director_bp, url_prefix="/director")
    app.register_blueprint(teacher_bp, url_prefix="/teacher")
    app.register_blueprint(student_bp, url_prefix="/student")
    app.register_blueprint(parent_bp, url_prefix="/parent")
    app.register_blueprint(reports_bp, url_prefix="/reports")
    app.register_blueprint(api_bp, url_prefix="/api/v1")

    # Rota raiz — redireciona para o dashboard correto
    from flask import redirect, url_for
    from flask_login import current_user

    @app.route("/")
    def index():
        if current_user.is_authenticated:
            return redirect(url_for(f"{current_user.role}.dashboard"))
        return redirect(url_for("auth.login"))

    # Páginas de erro
    @app.errorhandler(403)
    def forbidden(e):
        from flask import render_template
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        from flask import render_template
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        from flask import render_template
        return render_template("errors/500.html"), 500

    # Registra filtros de template customizados
    from .utils.helpers import register_template_filters
    register_template_filters(app)

    # Carrega modelos para que o Flask-Migrate os encontre
    with app.app_context():
        from . import models  # noqa: F401

    return app
