import logging
import os

import click
from flask import Flask
from flask_login import current_user
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import Config
from .extensions import csrf, db, login_manager, session_store
from .models import (
    EnargasCredentials,
    ImgToPdfJob,
    Proceso,
    RpaEnargasJob,
    Taller,
    User,
    Workspace,
)


def create_app():
    _configure_logging()

    app = Flask(__name__)
    app.config.from_object(Config)
    _validate_security_config(app)

    if app.config.get("IS_PRODUCTION"):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    session_store.init_app(app)

    from .auth import auth
    from .routes import main

    app.register_blueprint(auth)
    app.register_blueprint(main)

    @app.after_request
    def _prevent_cache(response):
        if current_user.is_authenticated and response.mimetype == "text/html":
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    @app.context_processor
    def _inject_workspace():
        name = app.config.get("APP_BRAND_NAME", "QuatroGNC")
        try:
            if current_user.is_authenticated and getattr(current_user, "workspace", None):
                name = current_user.workspace.name
            else:
                workspace = Workspace.query.first()
                if workspace and workspace.name:
                    name = workspace.name
        except Exception:
            pass
        return {"workspace_name": name}

    @app.cli.command("init-db")
    def init_db():
        with app.app_context():
            db.create_all()
        click.echo("Database initialized")

    @app.cli.command("seed-db")
    def seed_db():
        with app.app_context():
            db.create_all()
            _seed_data(app)
        click.echo("Database seeded")

    @app.cli.command("bootstrap-workspace")
    def bootstrap_workspace():
        with app.app_context():
            db.create_all()
            _bootstrap_workspace(app)
        click.echo("Workspace actualizado")

    return app


def _validate_security_config(app):
    if not app.config.get("IS_PRODUCTION"):
        return

    if app.config.get("SECRET_KEY") in ("", "dev-secret-change"):
        raise RuntimeError("SECRET_KEY debe configurarse en produccion.")
    if not app.config.get("ENCRYPTION_KEY"):
        raise RuntimeError("ENCRYPTION_KEY debe configurarse en produccion.")
    if not app.config.get("SESSION_COOKIE_SECURE"):
        raise RuntimeError("SESSION_COOKIE_SECURE debe ser true en produccion.")
    if app.config.get("SESSION_TYPE") == "filesystem":
        raise RuntimeError("SESSION_TYPE no puede ser filesystem en produccion.")


def _configure_logging():
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    root = logging.getLogger()
    root.setLevel(level)

    if not root.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s"
        )
        handler.setFormatter(formatter)
        root.addHandler(handler)


def _seed_data(app):
    if not app.config.get("ALLOW_SEED_DEMO"):
        return

    admin_user = app.config.get("DEFAULT_ADMIN_USER")
    admin_password = app.config.get("DEFAULT_ADMIN_PASSWORD")
    if not admin_user or not admin_password:
        return

    default_user = User.query.filter_by(username=admin_user).first()
    if not default_user:
        default_user = User(username=admin_user, role="admin")
        default_user.set_password(admin_password)
        db.session.add(default_user)
        db.session.commit()
    elif not default_user.role:
        default_user.role = "admin"
        db.session.commit()

    if not EnargasCredentials.query.filter_by(user_id=default_user.id).first():
        credentials = EnargasCredentials(
            user_id=default_user.id,
            enargas_user="demo_enargas",
        )
        credentials.set_password("demo_password")
        db.session.add(credentials)

    if not ImgToPdfJob.query.first():
        db.session.add(
            ImgToPdfJob(
                user_id=default_user.id,
                filename="inspeccion_abril.zip",
                page_count=18,
                status="done",
            )
        )
        db.session.add(
            ImgToPdfJob(
                user_id=default_user.id,
                filename="camara_03.zip",
                page_count=12,
                status="processing",
            )
        )

    if not RpaEnargasJob.query.first():
        db.session.add(
            RpaEnargasJob(
                user_id=default_user.id,
                patente="AB123CD",
                status="done",
                result_code="valid",
                pdf_filename="enargas_AB123CD.pdf",
            )
        )
        db.session.add(
            RpaEnargasJob(
                user_id=default_user.id,
                patente="XY987ZT",
                status="queued",
                result_code="pending",
                pdf_filename=None,
            )
        )

    if not Proceso.query.first():
        db.session.add(
            Proceso(
                user_id=default_user.id,
                patente="AA123BB",
                estado="completado",
                resultado="Revonar Oblea",
                pdf_filename="proceso_AA123BB.pdf",
            )
        )
        db.session.add(
            Proceso(
                user_id=default_user.id,
                patente="ABC123",
                estado="en proceso",
                resultado=None,
                pdf_filename=None,
            )
        )

    db.session.commit()

    _bootstrap_workspace(app)


def _bootstrap_workspace(app):
    name = app.config.get("APP_BRAND_NAME", "QuatroGNC")
    workspace = Workspace.query.first()
    if not workspace:
        workspace = Workspace(name=name)
        db.session.add(workspace)
        db.session.commit()

    User.query.filter(User.workspace_id.is_(None)).update(
        {User.workspace_id: workspace.id},
        synchronize_session=False,
    )
    User.query.filter(User.is_active.is_(None)).update(
        {User.is_active: True},
        synchronize_session=False,
    )
    User.query.filter(User.role.is_(None)).update(
        {User.role: "user"},
        synchronize_session=False,
    )
    admin_user = app.config.get("DEFAULT_ADMIN_USER")
    if admin_user:
        User.query.filter(User.username == admin_user).update(
            {User.role: "admin"},
            synchronize_session=False,
        )
    EnargasCredentials.query.filter(EnargasCredentials.workspace_id.is_(None)).update(
        {EnargasCredentials.workspace_id: workspace.id},
        synchronize_session=False,
    )
    Taller.query.filter(Taller.workspace_id.is_(None)).update(
        {Taller.workspace_id: workspace.id},
        synchronize_session=False,
    )
    Proceso.query.filter(Proceso.workspace_id.is_(None)).update(
        {Proceso.workspace_id: workspace.id},
        synchronize_session=False,
    )
    Proceso.query.filter(Proceso.created_by_user_id.is_(None)).update(
        {Proceso.created_by_user_id: Proceso.user_id},
        synchronize_session=False,
    )
    ImgToPdfJob.query.filter(ImgToPdfJob.workspace_id.is_(None)).update(
        {ImgToPdfJob.workspace_id: workspace.id},
        synchronize_session=False,
    )
    ImgToPdfJob.query.filter(ImgToPdfJob.created_by_user_id.is_(None)).update(
        {ImgToPdfJob.created_by_user_id: ImgToPdfJob.user_id},
        synchronize_session=False,
    )

    db.session.commit()
