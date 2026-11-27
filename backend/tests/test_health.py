from sqlalchemy.orm import sessionmaker

from app.db import get_session, make_engine
from app.main import app


def test_health_ok_with_database(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"


def test_health_503_when_database_unreachable(client):
    dead = sessionmaker(bind=make_engine("postgresql+psycopg://nobody:x@127.0.0.1:1/none?connect_timeout=1"))

    def broken_session():
        with dead() as s:
            yield s

    app.dependency_overrides[get_session] = broken_session
    try:
        r = client.get("/health")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 503
    assert r.json()["database"] == "unavailable"


def test_openapi_docs_available(client):
    assert client.get("/openapi.json").status_code == 200
