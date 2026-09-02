import os
from datetime import timedelta


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY")
    DEBUG = os.getenv("FLASK_ENV") == "development"

    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", os.getenv("SUPABASE_DB_URL", "sqlite:///mcq_battle.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size": 10,
        "max_overflow": 20,
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_use_lifo": True,
        "pool_timeout": 10,
    }

    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=1)
    JWT_TOKEN_LOCATION = ["cookies"]
    JWT_COOKIE_SECURE = os.getenv("FLASK_ENV", "production") != "development"
    JWT_COOKIE_SAMESITE = "Lax"
    JWT_CSRF_PROTECT = True
    JWT_CSRF_METHODS = ["POST", "PUT", "PATCH", "DELETE"]
    JWT_CSRF_IN_HEADERS = True
    JWT_ACCESS_COOKIE_NAME = "access_token_cookie"
    JWT_ACCESS_CSRF_COOKIE_NAME = "csrf_access_token"
    JWT_ACCESS_CSRF_HEADER_NAME = "X-CSRF-Token"

    SSO_JWT_SECRET: str = os.environ.get("JWT_SECRET", "")
    SSO_JWT_ALGORITHM: str = "HS256"
    PADIKKUNNUNDO_URL: str = os.environ.get("PADIKKUNNUNDO_URL", "https://padikkunnundo.app")

    CACHE_TYPE: str = os.environ.get("CACHE_TYPE", "SimpleCache")
    CACHE_DEFAULT_TIMEOUT: int = int(os.environ.get("CACHE_DEFAULT_TIMEOUT", "300"))
    CACHE_REDIS_URL: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

    @staticmethod
    def validate():
        """Raise at startup if any required secret is missing or set to a known-unsafe default."""
        errors = []
        if not os.getenv("SECRET_KEY"):
            errors.append("SECRET_KEY is not set.")
        if not os.getenv("JWT_SECRET_KEY"):
            errors.append("JWT_SECRET_KEY is not set.")
        if not os.getenv("JWT_SECRET"):
            errors.append("JWT_SECRET (SSO shared secret) is not set.")
        if os.getenv("JWT_SECRET") == "dev-only-jwt-secret":
            errors.append("JWT_SECRET is still set to the insecure dev default.")
        if errors:
            raise RuntimeError(
                "Production startup blocked — missing or insecure config:\n  "
                + "\n  ".join(errors)
            )
