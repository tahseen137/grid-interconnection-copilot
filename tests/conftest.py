from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import build_database_state, init_database
from app.main import create_app


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        app_env="test",
        database_url=f"sqlite:///{(tmp_path / 'grid-test.db').resolve()}",
    )


@pytest.fixture
def client(settings: Settings) -> Generator[TestClient, None, None]:
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def session(settings: Settings) -> Generator[Session, None, None]:
    database = build_database_state(settings)
    init_database(database)
    db_session = database.session_factory()
    try:
        yield db_session
    finally:
        db_session.close()
        database.engine.dispose()


@pytest.fixture
def auth_settings(tmp_path) -> Settings:
    return Settings(
        app_env="test",
        database_url=f"sqlite:///{(tmp_path / 'grid-auth-test.db').resolve()}",
        app_access_password="pilot-password",
        session_secret="test-session-secret",
    )


@pytest.fixture
def auth_client(auth_settings: Settings) -> Generator[TestClient, None, None]:
    app = create_app(auth_settings)
    with TestClient(app) as test_client:
        yield test_client
