"""
End-to-end smoke tests using an in-memory SQLite DB (swapped in via
dependency override) so tests don't require a real Postgres/S3 connection.

S3-dependent endpoints (attachments) are intentionally not covered here —
those are better tested against a mocked boto3 client (e.g. with moto) or
in a staging environment with a real bucket.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db

# StaticPool makes every connection reuse the same in-memory SQLite DB —
# without it, each new connection (i.e. each request) would get its own
# empty database and "no such table" errors would follow.
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


client = TestClient(app)


def _register_and_login(email="alice@example.com", password="strongpassword"):
    client.post(
        "/auth/register",
        json={"email": email, "full_name": "Alice", "password": password},
    )
    resp = client.post("/auth/login", data={"username": email, "password": password})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_health_check():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_register_and_login():
    headers = _register_and_login()
    resp = client.get("/users/me", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == "alice@example.com"


def test_duplicate_registration_fails():
    client.post(
        "/auth/register",
        json={"email": "bob@example.com", "full_name": "Bob", "password": "pw123456"},
    )
    resp = client.post(
        "/auth/register",
        json={"email": "bob@example.com", "full_name": "Bob2", "password": "pw123456"},
    )
    assert resp.status_code == 400


def test_project_and_task_lifecycle():
    headers = _register_and_login()

    resp = client.post(
        "/projects/", json={"name": "Website Revamp", "description": "Q3 project"}, headers=headers
    )
    assert resp.status_code == 201
    project_id = resp.json()["id"]

    resp = client.post(
        f"/projects/{project_id}/tasks",
        json={"title": "Design homepage", "priority": "high"},
        headers=headers,
    )
    assert resp.status_code == 201
    task_id = resp.json()["id"]
    assert resp.json()["status"] == "todo"

    resp = client.put(
        f"/tasks/{task_id}", json={"status": "in_progress"}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"

    resp = client.get(f"/projects/{project_id}/tasks", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_unauthorized_access_is_rejected():
    resp = client.get("/users/me")
    assert resp.status_code == 401


def test_cannot_access_other_users_project():
    headers_a = _register_and_login("owner@example.com", "password123")
    headers_b = _register_and_login("intruder@example.com", "password123")

    resp = client.post("/projects/", json={"name": "Private project"}, headers=headers_a)
    project_id = resp.json()["id"]

    resp = client.get(f"/projects/{project_id}", headers=headers_b)
    assert resp.status_code == 403
