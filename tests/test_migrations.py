from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def test_alembic_upgrade_creates_expected_schema(tmp_path) -> None:
    database_path = tmp_path / "migration-test.db"
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path.resolve()}")

    command.upgrade(config, "head")

    engine = create_engine(f"sqlite:///{database_path.resolve()}")
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    assert {"alembic_version", "users", "projects", "sites", "analysis_runs", "analysis_site_results"}.issubset(table_names)
    with engine.connect() as connection:
        version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    assert version == "20260326_02"
    engine.dispose()
