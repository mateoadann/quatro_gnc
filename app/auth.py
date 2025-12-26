import secrets
from urllib.parse import urlencode

import requests
from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import login_required, login_user, logout_user

from .extensions import db, login_manager, oauth
from .models import User


auth = Blueprint("auth", __name__)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@auth.route("/login", methods=["GET", "POST"])
def login():
    keycloak_enabled = current_app.config.get("KEYCLOAK_ENABLED")

    if keycloak_enabled:
        client = _get_keycloak_client()
        if not client:
            flash("Keycloak no esta configurado.", "error")
            return render_template("login.html", keycloak_enabled=False)

        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "").strip()
            token, userinfo, error = _keycloak_password_login(username, password)
            if error:
                flash(error, "error")
                return render_template("login.html", keycloak_enabled=True)

            user = _get_or_create_user(userinfo, username)
            if not user:
                flash("Usuario no autorizado en esta aplicacion.", "error")
                return render_template("login.html", keycloak_enabled=True)

            login_user(user)
            session["keycloak_token"] = token
            if token.get("id_token"):
                session["keycloak_id_token"] = token.get("id_token")
            session["keycloak_auth_flow"] = "password"
            return redirect(url_for("main.dashboard"))

        return render_template("login.html", keycloak_enabled=True)

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        user = User.query.filter_by(username=username).first()
        if not user or not user.check_password(password):
            flash("Credenciales invalidas.", "error")
        else:
            login_user(user)
            return redirect(url_for("main.dashboard"))

    return render_template("login.html", keycloak_enabled=False)


@auth.route("/logout")
@login_required
def logout():
    keycloak_enabled = current_app.config.get("KEYCLOAK_ENABLED")
    id_token = session.pop("keycloak_id_token", None)
    token = session.pop("keycloak_token", None)
    auth_flow = session.pop("keycloak_auth_flow", None)
    if token and not id_token:
        id_token = token.get("id_token")

    logout_user()
    if keycloak_enabled and id_token and auth_flow == "authorization_code":
        logout_url = _get_keycloak_logout_url()
        if logout_url:
            post_logout = current_app.config.get(
                "KEYCLOAK_POST_LOGOUT_REDIRECT_URI", ""
            ) or url_for("auth.login", _external=True)
            params = {
                "post_logout_redirect_uri": post_logout,
                "id_token_hint": id_token,
            }
            return redirect(f"{logout_url}?{urlencode(params)}")
    return redirect(url_for("auth.login"))


@auth.route("/login/keycloak")
def keycloak_login():
    client = _get_keycloak_client()
    if not current_app.config.get("KEYCLOAK_ENABLED") or not client:
        flash("Keycloak no esta configurado.", "error")
        return redirect(url_for("auth.login"))

    redirect_uri = current_app.config.get("KEYCLOAK_REDIRECT_URI") or url_for(
        "auth.keycloak_callback", _external=True
    )
    return client.authorize_redirect(redirect_uri)


@auth.route("/auth/keycloak/callback")
def keycloak_callback():
    client = _get_keycloak_client()
    if not current_app.config.get("KEYCLOAK_ENABLED") or not client:
        flash("Keycloak no esta configurado.", "error")
        return redirect(url_for("auth.login"))

    token = client.authorize_access_token()
    if not token:
        flash("No se pudo completar la autenticacion.", "error")
        return redirect(url_for("auth.login"))

    try:
        userinfo = client.parse_id_token(token)
    except Exception:
        userinfo = {}
    if not userinfo:
        userinfo = client.userinfo()

    user = _get_or_create_user(userinfo)
    if not user:
        flash("Usuario no autorizado en esta aplicacion.", "error")
        return redirect(url_for("auth.login"))

    login_user(user)
    session["keycloak_token"] = token
    if token.get("id_token"):
        session["keycloak_id_token"] = token.get("id_token")
    session["keycloak_auth_flow"] = "authorization_code"
    return redirect(url_for("main.dashboard"))


def _get_keycloak_client():
    return oauth.create_client("keycloak")


def _get_keycloak_logout_url():
    client = _get_keycloak_client()
    if client:
        metadata = client.load_server_metadata()
        if metadata:
            logout_url = metadata.get("end_session_endpoint")
            if logout_url:
                return logout_url

    base_url = current_app.config.get("KEYCLOAK_BASE_URL", "").rstrip("/")
    realm = current_app.config.get("KEYCLOAK_REALM", "").strip()
    if base_url and realm:
        return f"{base_url}/realms/{realm}/protocol/openid-connect/logout"
    return None


def _keycloak_password_login(username, password):
    client = _get_keycloak_client()
    if not client:
        return None, None, "Keycloak no esta configurado."
    metadata = client.load_server_metadata()
    token_url = metadata.get("token_endpoint")
    userinfo_url = metadata.get("userinfo_endpoint")

    if not token_url:
        return None, None, "No se encontro el endpoint de token en Keycloak."

    data = {
        "grant_type": "password",
        "client_id": current_app.config.get("KEYCLOAK_CLIENT_ID", ""),
        "username": username,
        "password": password,
        "scope": current_app.config.get("KEYCLOAK_SCOPE", "openid email profile"),
    }
    client_secret = current_app.config.get("KEYCLOAK_CLIENT_SECRET")
    if client_secret:
        data["client_secret"] = client_secret

    response = requests.post(token_url, data=data, timeout=10)
    if not response.ok:
        payload = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
        error = payload.get("error_description") or "Credenciales invalidas."
        return None, None, error

    token = response.json()
    userinfo = {}
    access_token = token.get("access_token")
    if userinfo_url and access_token:
        info_response = requests.get(
            userinfo_url,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        if info_response.ok:
            userinfo = info_response.json()

    return token, userinfo, None


def _get_or_create_user(userinfo, fallback_username=None):
    username = (
        userinfo.get("preferred_username")
        or userinfo.get("email")
        or userinfo.get("sub")
        or fallback_username
    )
    if not username:
        return None

    user = User.query.filter_by(username=username).first()
    first_name = userinfo.get("given_name") or ""
    last_name = userinfo.get("family_name") or ""
    if not user:
        if not current_app.config.get("KEYCLOAK_AUTO_PROVISION"):
            return None
        user = User(username=username)
        user.set_password(secrets.token_urlsafe(16))
        if first_name:
            user.first_name = first_name
        if last_name:
            user.last_name = last_name
        db.session.add(user)
        db.session.commit()
    else:
        updated = False
        if first_name and user.first_name != first_name:
            user.first_name = first_name
            updated = True
        if last_name and user.last_name != last_name:
            user.last_name = last_name
            updated = True
        if updated:
            db.session.commit()
    return user
