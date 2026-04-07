import time

from flask import Blueprint, flash, redirect, render_template, request, url_for, current_app
from flask_login import current_user, login_required, login_user, logout_user

from .extensions import login_manager
from .models import User


auth = Blueprint("auth", __name__)

# In-memory rate limiting stores (acceptable for 1-2 users / 1-2 workers)
_rate_limit_store: dict[str, tuple[int, float]] = {}  # ip -> (count, expires_at)
_fail_store: dict[str, tuple[int, float]] = {}  # username -> (count, expires_at)
_lockout_store: dict[str, float] = {}  # username -> expires_at


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def _get_client_ip() -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def _cleanup_expired() -> None:
    now = time.monotonic()
    expired_ips = [ip for ip, (_, exp) in _rate_limit_store.items() if exp <= now]
    for ip in expired_ips:
        del _rate_limit_store[ip]
    expired_users = [u for u, (_, exp) in _fail_store.items() if exp <= now]
    for u in expired_users:
        del _fail_store[u]
    expired_locks = [u for u, exp in _lockout_store.items() if exp <= now]
    for u in expired_locks:
        del _lockout_store[u]


def _check_rate_limit(ip: str) -> int | None:
    limit = current_app.config.get("LOGIN_RATE_LIMIT", 0)
    window = current_app.config.get("LOGIN_RATE_WINDOW", 0)
    if limit <= 0 or window <= 0:
        return None
    now = time.monotonic()
    entry = _rate_limit_store.get(ip)
    if entry and entry[1] > now:
        count = entry[0] + 1
        expires_at = entry[1]
    else:
        count = 1
        expires_at = now + window
    _rate_limit_store[ip] = (count, expires_at)
    if count > limit:
        return max(1, int(expires_at - now))
    return None


def _check_lockout(username: str) -> int | None:
    key = username.lower()
    now = time.monotonic()
    expires_at = _lockout_store.get(key)
    if expires_at and expires_at > now:
        return max(1, int(expires_at - now))
    if expires_at:
        del _lockout_store[key]
    return None


def _register_failure(username: str) -> int | None:
    limit = current_app.config.get("LOGIN_FAIL_LIMIT", 0)
    lock_seconds = current_app.config.get("LOGIN_LOCKOUT_SECONDS", 0)
    if limit <= 0 or lock_seconds <= 0:
        return None
    key = username.lower()
    now = time.monotonic()
    entry = _fail_store.get(key)
    if entry and entry[1] > now:
        count = entry[0] + 1
        expires_at = entry[1]
    else:
        count = 1
        expires_at = now + lock_seconds
    _fail_store[key] = (count, expires_at)
    if count >= limit:
        _lockout_store[key] = now + lock_seconds
        return lock_seconds
    return None


def _clear_failures(username: str) -> None:
    key = username.lower()
    _fail_store.pop(key, None)
    _lockout_store.pop(key, None)


@auth.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        ip = _get_client_ip()

        _cleanup_expired()

        retry_after = _check_rate_limit(ip)
        if retry_after:
            flash(
                f"Demasiados intentos. Espera {retry_after}s e intenta nuevamente.",
                "error",
            )
            return render_template("login.html")

        if username:
            locked_for = _check_lockout(username)
            if locked_for:
                flash(
                    f"Cuenta bloqueada. Espera {locked_for}s e intenta nuevamente.",
                    "error",
                )
                return render_template("login.html")

        user = User.query.filter_by(username=username).first()
        if user and not user.is_active:
            flash("Usuario desactivado. Contacta al administrador.", "error")
            return render_template("login.html")
        if not user or not user.check_password(password):
            if username:
                lock_for = _register_failure(username)
                if lock_for:
                    flash(
                        f"Cuenta bloqueada. Espera {lock_for}s e intenta nuevamente.",
                        "error",
                    )
                    return render_template("login.html")
            flash("Usuario o contrasena incorrectos.", "error")
            return render_template("login.html")

        if username:
            _clear_failures(username)

        login_user(user)
        return redirect(url_for("main.dashboard"))

    return render_template("login.html")


@auth.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
