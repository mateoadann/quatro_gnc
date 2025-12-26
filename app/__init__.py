import click
from flask import Flask

from .config import Config
from .extensions import db, login_manager
from .models import ImgToPdfJob, Proceso, RpaEnargasJob, User


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)

    from .auth import auth
    from .routes import main

    app.register_blueprint(auth)
    app.register_blueprint(main)

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

    return app


def _seed_data(app):
    default_user = User.query.filter_by(
        username=app.config["DEFAULT_ADMIN_USER"]
    ).first()
    if not default_user:
        default_user = User(username=app.config["DEFAULT_ADMIN_USER"])
        default_user.set_password(app.config["DEFAULT_ADMIN_PASSWORD"])
        default_user.enargas_user = "demo_enargas"
        default_user.set_enargas_password("demo_password")
        db.session.add(default_user)
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
