"""Tests run against a real PostgreSQL (docker compose `db` locally, a service container in CI).

A separate `<db>_test` database is created so tests never touch development data.
"""

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

BASE_URL = os.environ.get("DATABASE_URL", "postgresql+psycopg://jobmate:jobmate@localhost:5432/jobmate")
TEST_URL = make_url(BASE_URL).set(database=f"{make_url(BASE_URL).database}_test")

# Must be set before `app` is imported: app.db builds its engine at import time.
os.environ["DATABASE_URL"] = TEST_URL.render_as_string(hide_password=False)


def _ensure_test_database() -> None:
    admin = create_engine(make_url(BASE_URL).set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": TEST_URL.database}).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{TEST_URL.database}"'))
    admin.dispose()


def _alembic_config():
    from alembic.config import Config

    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = Config(os.path.join(here, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(here, "migrations"))
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
    return cfg


@pytest.fixture(scope="session")
def alembic_config():
    return _alembic_config()


@pytest.fixture(scope="session", autouse=True)
def migrated_database(alembic_config):
    from alembic import command

    _ensure_test_database()
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")
    yield


@pytest.fixture
def session():
    from app.db import SessionLocal

    with SessionLocal() as s:
        yield s
        s.rollback()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c
