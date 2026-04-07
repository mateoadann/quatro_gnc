from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from sqlalchemy.orm import deferred

from .extensions import db


class Workspace(db.Model):
    __tablename__ = "workspace"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    users = db.relationship("User", backref="workspace", lazy=True)
    img_jobs = db.relationship("ImgToPdfJob", backref="workspace", lazy=True)


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
    created_img_jobs = db.relationship(
        "ImgToPdfJob",
        foreign_keys="ImgToPdfJob.created_by_user_id",
        backref="creator",
        lazy=True,
    )

    def set_password(self, value):
        self.password_hash = generate_password_hash(value)

    def check_password(self, value):
        return check_password_hash(self.password_hash, value)


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
