"""Tests for the TaskTracker API.

Unit tests run with no database (the DB connection is faked).
Integration tests run only when RUN_DB_TESTS=1 and a real PostgreSQL is reachable
through the DB_* environment variables.
"""
import os

import psycopg2
import pytest

import app as app_module


@pytest.fixture()
def client():
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


# ---------- unit tests (no database needed) ----------

def test_health_returns_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_health_does_not_need_database(client, monkeypatch):
    def boom():
        raise AssertionError("/health must not touch the database")

    monkeypatch.setattr(app_module, "get_conn", boom)
    assert client.get("/health").status_code == 200


def test_ready_returns_503_when_db_down(client, monkeypatch):
    def fail():
        raise psycopg2.OperationalError("connection refused")

    monkeypatch.setattr(app_module, "get_conn", fail)
    resp = client.get("/ready")
    assert resp.status_code == 503
    assert resp.get_json()["status"] == "not ready"


def test_create_task_requires_title(client):
    resp = client.post("/api/tasks", json={"description": "no title"})
    assert resp.status_code == 400


def test_create_task_rejects_invalid_status(client):
    resp = client.post("/api/tasks", json={"title": "x", "status": "banana"})
    assert resp.status_code == 400


def test_create_task_rejects_non_json(client):
    resp = client.post("/api/tasks", data="not json", content_type="text/plain")
    assert resp.status_code == 400


# ---------- integration tests (need a real PostgreSQL) ----------

db_only = pytest.mark.skipif(
    os.getenv("RUN_DB_TESTS") != "1", reason="set RUN_DB_TESTS=1 with a reachable database"
)


@db_only
def test_ready_with_real_db(client):
    assert client.get("/ready").status_code == 200


@db_only
def test_task_crud_cycle(client):
    created = client.post("/api/tasks", json={"title": "pipeline test"})
    assert created.status_code == 201
    task_id = created.get_json()["id"]

    updated = client.put(f"/api/tasks/{task_id}", json={"status": "done"})
    assert updated.status_code == 200
    assert updated.get_json()["status"] == "done"

    assert any(t["id"] == task_id for t in client.get("/api/tasks").get_json())

    assert client.delete(f"/api/tasks/{task_id}").status_code == 204
    assert client.delete(f"/api/tasks/{task_id}").status_code == 404
