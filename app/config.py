import os
import re

from dotenv import load_dotenv

load_dotenv()

_basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
_default_db_path = os.path.join(_basedir, "data", "quatro_gnc.db")
_DEFAULT_SQLITE_URI = f"sqlite:///{_default_db_path}"


class Config:
    APP_ENV = os.getenv("APP_ENV", os.getenv("FLASK_ENV", "development")).lower()
    IS_PRODUCTION = APP_ENV == "production"
    APP_BRAND_NAME = os.getenv("APP_BRAND_NAME", "QuatroGNC")
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change")
    # Neon hands out postgres:// URLs; SQLAlchemy needs the psycopg (v3) driver name
    SQLALCHEMY_DATABASE_URI = re.sub(
        r"^postgres(ql)?://", "postgresql+psycopg://", os.getenv("DATABASE_URL", _DEFAULT_SQLITE_URI)
    )
    # Serverless instances sit idle between requests; drop dead connections instead of erroring
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 300}
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    DEFAULT_ADMIN_USER = os.getenv("DEFAULT_ADMIN_USER", "")
    DEFAULT_ADMIN_PASSWORD = os.getenv("DEFAULT_ADMIN_PASSWORD", "")
    ALLOW_SEED_DEMO = (
        os.getenv("ALLOW_SEED_DEMO", "false" if IS_PRODUCTION else "true").lower()
        == "true"
    )
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = os.getenv(
        "SESSION_COOKIE_SECURE",
        "true" if IS_PRODUCTION else "false",
    ).lower() == "true"
    SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = SESSION_COOKIE_SAMESITE

    WTF_CSRF_ENABLED = os.getenv("WTF_CSRF_ENABLED", "true").lower() == "true"
    WTF_CSRF_TIME_LIMIT = int(os.getenv("WTF_CSRF_TIME_LIMIT", "3600"))

    LOGIN_RATE_LIMIT = int(os.getenv("LOGIN_RATE_LIMIT", "5"))
    LOGIN_RATE_WINDOW = int(os.getenv("LOGIN_RATE_WINDOW", "60"))
    LOGIN_FAIL_LIMIT = int(os.getenv("LOGIN_FAIL_LIMIT", "5"))
    LOGIN_LOCKOUT_SECONDS = int(os.getenv("LOGIN_LOCKOUT_SECONDS", "600"))
    CRON_SECRET = os.getenv("CRON_SECRET", "")
    JOB_RETENTION_DAYS = int(os.getenv("JOB_RETENTION_DAYS", "20"))
