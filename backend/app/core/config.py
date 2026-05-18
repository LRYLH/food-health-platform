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

    wechat_app_id: str = ""
    wechat_app_secret: str = ""
    wechat_jscode2session_url: str = "https://api.weixin.qq.com/sns/jscode2session"

    upload_dir: Path = Path("uploads")
    model_io_dir: Path = Path("model_io")
    cors_origins: list[str] = ["*"]
    response_envelope_enabled: bool = False
    algorithm_enabled: bool = True
    algorithm_module_dir: Path | None = None

    @property
    def vision_input_dir(self) -> Path:
        return self.model_io_dir / "vision_input"

    @property
    def vision_output_dir(self) -> Path:
        return self.model_io_dir / "vision_output"

    @property
    def rag_output_dir(self) -> Path:
        return self.model_io_dir / "rag_output"

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
