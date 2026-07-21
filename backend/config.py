import os
from datetime import timedelta


class Config:
    """Base configuration class for the Flask backend.

    Security rule: do NOT hardcode secrets in code.
    SECRET_KEY and JWT_SECRET_KEY must be provided via environment variables.
    """

    # General Config
    SECRET_KEY = os.getenv("SECRET_KEY")
    DEBUG = os.getenv("FLASK_ENV") == "development"

    # Database Config
    # Support Supabase or standard Postgres via DATABASE_URL / SUPABASE_DB_URL
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", os.getenv("SUPABASE_DB_URL", "sqlite:///mcq_battle.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Connection Pooling for PostgreSQL performance
    # These settings optimize throughput and reduce latency for concurrent requests
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size": 10,           # Keep 10 persistent connections ready
        "max_overflow": 20,        # Allow up to 20 additional connections under load
        "pool_pre_ping": True,     # Verify connections are alive before handing them out
        "pool_recycle": 300,       # Recycle connections every 5 minutes to prevent stale connections
        "pool_use_lifo": True,     # LIFO prevents connection storms on restart
        "pool_timeout": 10,        # Wait max 10 seconds for a connection from pool
    }

    # JWT Config
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=1)

    # Shared SSO secret for padikkunnundo.app integration
    SSO_JWT_SECRET: str = os.environ.get("JWT_SECRET", "dev-only-jwt-secret")
    SSO_JWT_ALGORITHM: str = "HS256"

    # Cookie-based secure JWT with CSRF Double-Submit token protection
    JWT_TOKEN_LOCATION = ["cookies"]
    JWT_COOKIE_SECURE = os.getenv("FLASK_ENV", "development") == "production"
    JWT_COOKIE_SAMESITE = "Lax"
    JWT_CSRF_PROTECT = True
    JWT_CSRF_METHODS = ["POST", "PUT", "PATCH", "DELETE"]  # GET requests are exempt
    JWT_CSRF_IN_HEADERS = True
    JWT_ACCESS_COOKIE_NAME = "access_token_cookie"
    JWT_ACCESS_CSRF_COOKIE_NAME = "csrf_access_token"
    JWT_ACCESS_CSRF_HEADER_NAME = "X-CSRF-Token"

