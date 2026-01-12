from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from sqlalchemy.orm import deferred

from .extensions import db
from .utils import decrypt_value, encrypt_value


class Workspace(db.Model):
    __tablename__ = "workspace"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    users = db.relationship("User", backref="workspace", lazy=True)
    procesos = db.relationship("Proceso", backref="workspace", lazy=True)
    talleres = db.relationship("Taller", backref="workspace", lazy=True)
    img_jobs = db.relationship("ImgToPdfJob", backref="workspace", lazy=True)
    enargas_credentials = db.relationship(
        "EnargasCredentials", backref="workspace", lazy=True
    )


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspace.id"), nullable=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(120), nullable=True)
    last_name = db.Column(db.String(120), nullable=True)
    role = db.Column(db.String(20), nullable=False, default="user")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    img_jobs = db.relationship(
        "ImgToPdfJob",
        backref="user",
        lazy=True,
        foreign_keys="ImgToPdfJob.user_id",
    )
    rpa_jobs = db.relationship("RpaEnargasJob", backref="user", lazy=True)
    procesos = db.relationship(
        "Proceso",
        backref="user",
        lazy=True,
        foreign_keys="Proceso.user_id",
    )
    created_processes = db.relationship(
        "Proceso",
        foreign_keys="Proceso.created_by_user_id",
        backref="creator",
        lazy=True,
    )
    created_img_jobs = db.relationship(
        "ImgToPdfJob",
        foreign_keys="ImgToPdfJob.created_by_user_id",
        backref="creator",
        lazy=True,
    )
    enargas_credentials = db.relationship(
        "EnargasCredentials", backref="user", uselist=False, lazy=True
    )
    talleres = db.relationship("Taller", backref="user", lazy=True)

    def set_password(self, value):
        self.password_hash = generate_password_hash(value)

    def check_password(self, value):
        return check_password_hash(self.password_hash, value)

class EnargasCredentials(db.Model):
    __tablename__ = "enargas_credenciales"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, unique=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspace.id"), nullable=True)
    enargas_user = db.Column(db.String(120), nullable=False)
    enargas_password_encrypted = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def set_password(self, value):
        self.enargas_password_encrypted = encrypt_value(value)

    def get_password(self):
        return decrypt_value(self.enargas_password_encrypted)


class ImgToPdfJob(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspace.id"), nullable=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    filename = db.Column(db.String(255), nullable=False)
    page_count = db.Column(db.Integer, default=0)
    status = db.Column(db.String(40), default="pending")
    pdf_filename = db.Column(db.String(255), nullable=True)
    pdf_data = deferred(db.Column(db.LargeBinary, nullable=True))
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class RpaEnargasJob(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    patente = db.Column(db.String(40), nullable=False)
    status = db.Column(db.String(40), default="queued")
    result_code = db.Column(db.String(40), nullable=True)
    pdf_filename = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Proceso(db.Model):
    __tablename__ = "proceso"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspace.id"), nullable=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    taller_id = db.Column(db.Integer, db.ForeignKey("taller.id"), nullable=True)
    patente = db.Column(db.String(10), nullable=False)
    estado = db.Column(db.String(20), nullable=False, default="en proceso")
    resultado = db.Column(db.String(30), nullable=True)
    pdf_data = deferred(db.Column(db.LargeBinary, nullable=True))
    pdf_filename = db.Column(db.String(255), nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Taller(db.Model):
    __tablename__ = "taller"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspace.id"), nullable=True)
    nombre = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    procesos = db.relationship("Proceso", backref="taller", lazy=True)

    __table_args__ = (
        db.UniqueConstraint("user_id", "nombre", name="uq_taller_user_nombre"),
    )
