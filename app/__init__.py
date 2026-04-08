import logging
import os
from datetime import datetime, timedelta

import click
from flask import Flask
from flask_login import current_user
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import Config
from .extensions import csrf, db, login_manager, session_store
from .models import (
    ImgToPdfJob,
    User,
    Workspace,
)


def create_app():
    _configure_logging()

    app = Flask(__name__)
    app.config.from_object(Config)
    _validate_security_config(app)

    # Ensure flask_sessions directory exists for filesystem sessions
    session_dir = app.config.get("SESSION_FILE_DIR")
    if session_dir:
        os.makedirs(session_dir, exist_ok=True)

    # Ensure data/ directory exists for SQLite database
    db_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if db_uri.startswith("sqlite:///"):
        db_path = db_uri.replace("sqlite:///", "", 1)
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

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
            # Ensure data/ directory exists for SQLite
            uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
            if uri.startswith("sqlite:///"):
                db_path = uri.replace("sqlite:///", "", 1)
                db_dir = os.path.dirname(db_path)
                if db_dir:
                    os.makedirs(db_dir, exist_ok=True)
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

    @app.cli.command("cleanup-old-jobs")
    def cleanup_old_jobs():
        """Delete ImgToPdfJob records older than 20 days."""
        with app.app_context():
            try:
                cutoff = datetime.utcnow() - timedelta(days=20)
                deleted = (
                    db.session.query(ImgToPdfJob)
                    .filter(ImgToPdfJob.created_at < cutoff)
                    .delete(synchronize_session=False)
                )
                db.session.commit()
                click.echo(f"Cleanup: {deleted} jobs eliminados (anteriores a {cutoff.date()}).")
            except Exception as e:
                db.session.rollback()
                click.echo(f"Error durante el cleanup: {e}", err=True)

    return app


def _validate_security_config(app):
    if not app.config.get("IS_PRODUCTION"):
        return

    if app.config.get("SECRET_KEY") in ("", "dev-secret-change"):
        raise RuntimeError("SECRET_KEY debe configurarse en produccion.")
    if not app.config.get("SESSION_COOKIE_SECURE"):
        raise RuntimeError("SESSION_COOKIE_SECURE debe ser true en produccion.")


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
    ImgToPdfJob.query.filter(ImgToPdfJob.workspace_id.is_(None)).update(
        {ImgToPdfJob.workspace_id: workspace.id},
        synchronize_session=False,
    )
    ImgToPdfJob.query.filter(ImgToPdfJob.created_by_user_id.is_(None)).update(
        {ImgToPdfJob.created_by_user_id: ImgToPdfJob.user_id},
        synchronize_session=False,
    )

    db.session.commit()
