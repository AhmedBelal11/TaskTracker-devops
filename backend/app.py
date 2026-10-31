"""TaskTracker API - a small Flask service used as the target for a DevOps project.

Configuration comes ONLY from environment variables (12-factor style):

    DB_HOST       (default: localhost)
    DB_PORT       (default: 5432)
    DB_NAME       (default: tasktracker)
    DB_USER       (default: tasktracker)
    DB_PASSWORD   (required for real use, no default on purpose)
    APP_ENV       (default: development)
    LOG_LEVEL     (default: INFO)
    PORT          (default: 5000)
"""
import logging
import os

import psycopg2
import psycopg2.extras
from flask import Flask, jsonify, request

APP_VERSION = os.getenv("APP_VERSION", "dev")

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("tasktracker")

app = Flask(__name__)

VALID_STATUSES = {"todo", "in_progress", "done"}


def get_conn():
    """Open a new DB connection using env vars. Short timeout so probes fail fast."""
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "tasktracker"),
        user=os.getenv("DB_USER", "tasktracker"),
        password=os.getenv("DB_PASSWORD", ""),
        connect_timeout=3,
    )


# ---------- health endpoints ----------

@app.get("/health")
def health():
    """Liveness: the process is up. Deliberately does NOT touch the database."""
    return jsonify(status="ok", version=APP_VERSION, env=os.getenv("APP_ENV", "development"))


@app.get("/ready")
def ready():
    """Readiness: the app can actually serve traffic (database reachable)."""
    try:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        finally:
            conn.close()
        return jsonify(status="ready")
    except Exception as exc:  # noqa: BLE001
        log.error("readiness check failed: %s", exc)
        return jsonify(status="not ready", reason="database unreachable"), 503


# ---------- API ----------

def _validate(payload, partial=False):
    if not isinstance(payload, dict):
        return "JSON body required"
    if not partial and not str(payload.get("title", "")).strip():
        return "title is required"
    if "title" in payload and not str(payload["title"]).strip():
        return "title cannot be empty"
    if "status" in payload and payload["status"] not in VALID_STATUSES:
        return f"status must be one of {sorted(VALID_STATUSES)}"
    return None


@app.get("/api/tasks")
def list_tasks():
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id, title, description, status, created_at FROM tasks ORDER BY id")
            rows = cur.fetchall()
        return jsonify(rows)
    finally:
        conn.close()


@app.post("/api/tasks")
def create_task():
    payload = request.get_json(silent=True)
    error = _validate(payload)
    if error:
        return jsonify(error=error), 400
    conn = get_conn()
    try:
        with conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO tasks (title, description, status) VALUES (%s, %s, %s) "
                "RETURNING id, title, description, status, created_at",
                (
                    payload["title"].strip(),
                    payload.get("description", ""),
                    payload.get("status", "todo"),
                ),
            )
            row = cur.fetchone()
        log.info("created task id=%s", row["id"])
        return jsonify(row), 201
    finally:
        conn.close()


@app.put("/api/tasks/<int:task_id>")
def update_task(task_id):
    payload = request.get_json(silent=True)
    error = _validate(payload, partial=True)
    if error:
        return jsonify(error=error), 400
    conn = get_conn()
    try:
        with conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "UPDATE tasks SET title = COALESCE(%s, title), "
                "description = COALESCE(%s, description), "
                "status = COALESCE(%s, status) WHERE id = %s "
                "RETURNING id, title, description, status, created_at",
                (payload.get("title"), payload.get("description"), payload.get("status"), task_id),
            )
            row = cur.fetchone()
        if row is None:
            return jsonify(error="task not found"), 404
        return jsonify(row)
    finally:
        conn.close()


@app.delete("/api/tasks/<int:task_id>")
def delete_task(task_id):
    conn = get_conn()
    try:
        with conn, conn.cursor() as cur:
            cur.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
            deleted = cur.rowcount
        if not deleted:
            return jsonify(error="task not found"), 404
        return "", 204
    finally:
        conn.close()


@app.errorhandler(psycopg2.OperationalError)
def db_down(exc):
    log.error("database error: %s", exc)
    return jsonify(error="database unavailable"), 503


if __name__ == "__main__":
    # Dev server only. In containers, use gunicorn (see requirements.txt).
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
