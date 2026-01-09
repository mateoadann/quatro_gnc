import os

import redis

from dotenv import load_dotenv

load_dotenv()


class Config:
    APP_ENV = os.getenv("APP_ENV", os.getenv("FLASK_ENV", "development")).lower()
    IS_PRODUCTION = APP_ENV == "production"
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", "postgresql+psycopg://postgres:postgres@db:5432/quatro_gnc"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }

    DEFAULT_ADMIN_USER = os.getenv("DEFAULT_ADMIN_USER", "")
    DEFAULT_ADMIN_PASSWORD = os.getenv("DEFAULT_ADMIN_PASSWORD", "")
    ALLOW_SEED_DEMO = (
        os.getenv("ALLOW_SEED_DEMO", "false" if IS_PRODUCTION else "true").lower()
        == "true"
    )
    ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "")

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

    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    SESSION_TYPE = os.getenv(
        "SESSION_TYPE",
        "redis" if IS_PRODUCTION else "filesystem",
    )
    SESSION_PERMANENT = False
    SESSION_USE_SIGNER = True
    SESSION_REDIS = redis.from_url(REDIS_URL) if SESSION_TYPE == "redis" else None
    RQ_DEFAULT_TIMEOUT = int(os.getenv("RQ_DEFAULT_TIMEOUT", "900"))
    RPA_PER_PAGE = int(os.getenv("RPA_PER_PAGE", "10"))
    RPA_STALE_MINUTES = int(os.getenv("RPA_STALE_MINUTES", "15"))
    LOGIN_RATE_LIMIT = int(os.getenv("LOGIN_RATE_LIMIT", "5"))
    LOGIN_RATE_WINDOW = int(os.getenv("LOGIN_RATE_WINDOW", "60"))
    LOGIN_FAIL_LIMIT = int(os.getenv("LOGIN_FAIL_LIMIT", "5"))
    LOGIN_LOCKOUT_SECONDS = int(os.getenv("LOGIN_LOCKOUT_SECONDS", "600"))
