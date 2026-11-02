from datetime import datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for, current_app
from flask_login import current_user, login_required, login_user, logout_user

from .extensions import db, login_manager
from .models import LoginThrottle, User


auth = Blueprint("auth", __name__)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def _get_client_ip() -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


# Counters live in the DB: serverless instances don't share memory.
# ponytail: concurrent first attempts for the same key can race on insert (500),
# switch to an ON CONFLICT upsert if that ever shows up in logs.
def _cleanup_expired() -> None:
    LoginThrottle.query.filter(LoginThrottle.expires_at <= datetime.utcnow()).delete()
    db.session.commit()


def _bump(key: str, window: int) -> LoginThrottle:
    now = datetime.utcnow()
    entry = db.session.get(LoginThrottle, key)
    if entry is None:
        entry = LoginThrottle(key=key, count=0, expires_at=now + timedelta(seconds=window))
        db.session.add(entry)
    entry.count += 1
    db.session.commit()
    return entry


def _seconds_left(entry: LoginThrottle) -> int:
    return max(1, int((entry.expires_at - datetime.utcnow()).total_seconds()))


def _check_rate_limit(ip: str) -> int | None:
    limit = current_app.config.get("LOGIN_RATE_LIMIT", 0)
    window = current_app.config.get("LOGIN_RATE_WINDOW", 0)
    if limit <= 0 or window <= 0:
        return None
    entry = _bump(f"ip:{ip}", window)
    if entry.count > limit:
        return _seconds_left(entry)
    return None


def _check_lockout(username: str) -> int | None:
    limit = current_app.config.get("LOGIN_FAIL_LIMIT", 0)
    entry = db.session.get(LoginThrottle, f"user:{username.lower()}")
    if limit > 0 and entry and entry.count >= limit:
        return _seconds_left(entry)
    return None


def _register_failure(username: str) -> int | None:
    limit = current_app.config.get("LOGIN_FAIL_LIMIT", 0)
    lock_seconds = current_app.config.get("LOGIN_LOCKOUT_SECONDS", 0)
    if limit <= 0 or lock_seconds <= 0:
        return None
    entry = _bump(f"user:{username.lower()}", lock_seconds)
    if entry.count >= limit:
        entry.expires_at = datetime.utcnow() + timedelta(seconds=lock_seconds)
        db.session.commit()
        return lock_seconds
    return None


def _clear_failures(username: str) -> None:
    LoginThrottle.query.filter_by(key=f"user:{username.lower()}").delete()
    db.session.commit()


@auth.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        # User.username is String(80); longer input would overflow login_throttle.key
        username = request.form.get("username", "").strip()[:80]
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
