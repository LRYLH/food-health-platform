from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Food Health Platform API"
    api_v1_prefix: str = "/api/v1"
    environment: str = "development"
    debug: bool = True

    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3307
    mysql_user: str = "root"
    mysql_password: str = ""
    mysql_database: str = "food_health_platform"

    redis_host: str = "127.0.0.1"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str | None = None

    secret_key: str = Field(
        default="",
        description="JWT signing key. Override in production.",
    )
    access_token_expire_minutes: int = 30
    refresh_token_expire_minutes: int = 60 * 24 * 14
    jwt_algorithm: str = "HS256"
    access_token_cookie_name: str = "access_token"
    refresh_token_cookie_name: str = "refresh_token"
    auth_cookie_secure: bool = False
    auth_cookie_samesite: str = "lax"
    auth_cookie_domain: str | None = None

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_from_name: str = "Food Health Platform"
    smtp_use_tls: bool = True

    email_code_expire_minutes: int = 10
    email_code_length: int = 6
    email_code_resend_interval_seconds: int = 60
    email_code_max_verify_attempts: int = 5

    upload_dir: Path = Path("uploads")
    cors_origins: list[str] = ["*"]

    @property
    def database_url(self) -> str:
        return (
            "mysql+pymysql://"
            f"{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
            "?charset=utf8mb4"
        )

    @property
    def redis_url(self) -> str:
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
