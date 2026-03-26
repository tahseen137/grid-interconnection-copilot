from functools import lru_cache
from pathlib import Path

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Grid Interconnection & Energy Siting Copilot"
    app_env: str = "development"
    database_url: str | None = None
    database_path: Path = Path("data/grid_interconnection.db")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite:///{self.database_path.resolve()}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
