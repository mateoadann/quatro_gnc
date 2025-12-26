from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import login_required, login_user, logout_user

from .extensions import db, login_manager
from .models import User


auth = Blueprint("auth", __name__)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@auth.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        user = User.query.filter_by(username=username).first()
        if not user or not user.check_password(password):
            flash("Credenciales invalidas.", "error")
        else:
            login_user(user)
            return redirect(url_for("main.dashboard"))

    keycloak_enabled = current_app.config.get("KEYCLOAK_ENABLED")
    return render_template("login.html", keycloak_enabled=keycloak_enabled)


@auth.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


@auth.route("/login/keycloak")
def keycloak_login():
    flash("Integracion con Keycloak pendiente de configurar.", "warning")
    return redirect(url_for("auth.login"))
