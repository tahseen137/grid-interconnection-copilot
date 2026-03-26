from types import SimpleNamespace

from sqlalchemy import inspect

from app.config import Settings
from app.db import build_database_state, database_is_ready, init_database


def test_build_database_state_supports_non_sqlite_urls() -> None:
    settings = Settings(
        app_env="test",
        database_url="postgresql+psycopg://user:pass@localhost/testdb",
    )

    database = build_database_state(settings)

    assert database.engine.url.drivername == "postgresql+psycopg"
    database.engine.dispose()


def test_settings_normalize_render_postgres_urls() -> None:
    settings = Settings(
        app_env="test",
        database_url="postgresql://user:pass@localhost/testdb",
    )

    assert settings.resolved_database_url == "postgresql+psycopg://user:pass@localhost/testdb"


def test_init_database_can_skip_schema_creation(tmp_path) -> None:
    settings = Settings(
        app_env="test",
        database_url=f"sqlite:///{(tmp_path / 'skip-schema.db').resolve()}",
    )
    database = build_database_state(settings)

    init_database(database, auto_create_schema=False)

    inspector = inspect(database.engine)
    assert "projects" not in inspector.get_table_names()
    assert database_is_ready(database) is True
    database.engine.dispose()


def test_database_is_ready_returns_false_on_connection_errors() -> None:
    class BrokenEngine:
        def connect(self):
            raise RuntimeError("broken connection")

    assert database_is_ready(SimpleNamespace(engine=BrokenEngine())) is False
