from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "HRMS"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"

    # Database. Example: mysql+pymysql://hrms_user:password@localhost:3306/hrms_db
    DATABASE_URL: str = f"sqlite:///{(BASE_DIR / 'hrms_dev.db').as_posix()}"
    DB_ECHO: bool = False

    # JWT
    JWT_SECRET_KEY: str = Field(default="change-me-in-production-please-use-a-long-random-string", min_length=32)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    REFRESH_COOKIE_NAME: str = "hrms_refresh"
    COOKIE_SECURE: bool = False  # set True behind HTTPS
    PASSWORD_RESET_EXPIRE_HOURS: int = 72

    # Login protection
    MAX_FAILED_LOGINS: int = 5
    LOCKOUT_MINUTES: int = 15

    # CORS / frontend
    FRONTEND_URL: str = "http://localhost:5173"
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Time zone used for attendance & payroll calendars
    APP_TIMEZONE: str = "Asia/Kolkata"

    # File uploads
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    MAX_UPLOAD_MB: int = 5

    # Email (SMTP is optional: when SMTP_HOST is empty emails are only logged)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = True
    MAIL_FROM: str = "HRMS <no-reply@hrms.local>"

    @field_validator("UPLOAD_DIR", mode="before")
    @classmethod
    def _resolve_upload_dir(cls, v):
        p = Path(v)
        return p if p.is_absolute() else BASE_DIR / p

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")

    @property
    def smtp_enabled(self) -> bool:
        return bool(self.SMTP_HOST)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
