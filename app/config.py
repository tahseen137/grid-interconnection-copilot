from functools import lru_cache
from pathlib import Path

from pydantic import computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Grid Interconnection & Energy Siting Copilot"
    app_env: str = "development"
    database_url: str | None = None
    database_path: Path = Path("data/grid_interconnection.db")
    app_access_password: str | None = None
    bootstrap_admin_username: str | None = None
    bootstrap_admin_password: str | None = None
    session_secret: str | None = None
    session_max_age_seconds: int = 60 * 60 * 12
    max_login_attempts: int = 5
    login_lockout_minutes: int = 15
    trusted_hosts: str = "*"
    enable_gzip: bool = True
    enforce_https: bool = False
    auto_create_schema: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_auth_configuration(self) -> "Settings":
        bootstrap_present = bool(self.bootstrap_admin_username or self.bootstrap_admin_password)
        if bootstrap_present and not (self.bootstrap_admin_username and self.bootstrap_admin_password):
            raise ValueError("bootstrap_admin_username and bootstrap_admin_password must be configured together")
        if (self.app_access_password or bootstrap_present) and not self.session_secret:
            raise ValueError("session_secret is required when app_access_password is configured")
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite:///{self.database_path.resolve()}"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def legacy_password_login_enabled(self) -> bool:
        return bool(self.app_access_password)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def bootstrap_admin_configured(self) -> bool:
        return bool(self.bootstrap_admin_username and self.bootstrap_admin_password)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def allowed_hosts(self) -> list[str]:
        hosts = [host.strip() for host in self.trusted_hosts.split(",") if host.strip()]
        return hosts or ["*"]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def session_https_only(self) -> bool:
        return self.app_env == "production" or self.enforce_https


@lru_cache
def get_settings() -> Settings:
    return Settings()
