from flask import Blueprint, flash, redirect, render_template, request, url_for, current_app
from flask_login import current_user, login_required, login_user, logout_user
from redis import Redis
from redis.exceptions import RedisError

from .extensions import login_manager
from .models import User


auth = Blueprint("auth", __name__)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def _get_client_ip() -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def _get_redis_client() -> Redis | None:
    redis_url = current_app.config.get("REDIS_URL")
    if not redis_url:
        return None
    try:
        return Redis.from_url(redis_url)
    except RedisError:
        return None


def _get_ttl_seconds(client: Redis, key: str) -> int | None:
    ttl = client.ttl(key)
    if ttl is None or ttl < 0:
        return None
    return ttl


def _check_rate_limit(client: Redis, ip: str) -> int | None:
    limit = current_app.config.get("LOGIN_RATE_LIMIT", 0)
    window = current_app.config.get("LOGIN_RATE_WINDOW", 0)
    if limit <= 0 or window <= 0:
        return None
    key = f"login:rate:{ip}"
    count = client.incr(key)
    if count == 1:
        client.expire(key, window)
    if count > limit:
        return _get_ttl_seconds(client, key) or window
    return None


def _check_lockout(client: Redis, username: str) -> int | None:
    lock_key = f"login:lock:{username.lower()}"
    ttl = _get_ttl_seconds(client, lock_key)
    if ttl:
        return ttl
    return None


def _register_failure(client: Redis, username: str) -> int | None:
    limit = current_app.config.get("LOGIN_FAIL_LIMIT", 0)
    lock_seconds = current_app.config.get("LOGIN_LOCKOUT_SECONDS", 0)
    if limit <= 0 or lock_seconds <= 0:
        return None
    fail_key = f"login:fail:{username.lower()}"
    count = client.incr(fail_key)
    if count == 1:
        client.expire(fail_key, lock_seconds)
    if count >= limit:
        lock_key = f"login:lock:{username.lower()}"
        client.setex(lock_key, lock_seconds, count)
        return lock_seconds
    return None


def _clear_failures(client: Redis, username: str) -> None:
    keys = [
        f"login:fail:{username.lower()}",
        f"login:lock:{username.lower()}",
    ]
    client.delete(*keys)


@auth.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        client = _get_redis_client()
        ip = _get_client_ip()
        if client:
            try:
                retry_after = _check_rate_limit(client, ip)
                if retry_after:
                    flash(
                        f"Demasiados intentos. Espera {retry_after}s e intenta nuevamente.",
                        "error",
                    )
                    return render_template("login.html")
                if username:
                    locked_for = _check_lockout(client, username)
                    if locked_for:
                        flash(
                            f"Cuenta bloqueada. Espera {locked_for}s e intenta nuevamente.",
                            "error",
                        )
                        return render_template("login.html")
            except RedisError:
                client = None

        user = User.query.filter_by(username=username).first()
        if user and not user.is_active:
            flash("Usuario desactivado. Contacta al administrador.", "error")
            return render_template("login.html")
        if not user or not user.check_password(password):
            if client and username:
                try:
                    lock_for = _register_failure(client, username)
                except RedisError:
                    lock_for = None
                if lock_for:
                    flash(
                        f"Cuenta bloqueada. Espera {lock_for}s e intenta nuevamente.",
                        "error",
                    )
                    return render_template("login.html")
            flash("Usuario o contrasena incorrectos.", "error")
            return render_template("login.html")

        if client and username:
            try:
                _clear_failures(client, username)
            except RedisError:
                pass

        login_user(user)
        return redirect(url_for("main.dashboard"))

    return render_template("login.html")


@auth.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
