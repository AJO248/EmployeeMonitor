import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    jwt_secret: str = os.getenv(
        "EM_JWT_SECRET", "development-only-change-me-before-production"
    )
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = _int_env("EM_ACCESS_TOKEN_MINUTES", 60)
    ingest_token: str = os.getenv("EM_INGEST_TOKEN", "development-ingest-token")
    ingest_rate_limit: int = _int_env("EM_INGEST_RATE_LIMIT_PER_MINUTE", 120)
    bootstrap_admin_username: str = os.getenv("EM_ADMIN_USERNAME", "admin")
    bootstrap_admin_password: str = os.getenv("EM_ADMIN_PASSWORD", "change-me")
    create_tables: bool = os.getenv("EM_CREATE_TABLES", "true").lower() == "true"
    cookie_secure: bool = os.getenv("EM_COOKIE_SECURE", "false").lower() == "true"


settings = Settings()
