-- Schema for TaskTracker. Run once against an empty database.
-- (Deciding HOW this gets applied in Docker/Kubernetes is part of your job.)

CREATE TABLE IF NOT EXISTS tasks (
    id          SERIAL PRIMARY KEY,
    title       VARCHAR(200) NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status      VARCHAR(20) NOT NULL DEFAULT 'todo'
                CHECK (status IN ('todo', 'in_progress', 'done')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO tasks (title, description, status) VALUES
    ('Set up repository', 'Create the GitHub repo and branch strategy', 'done'),
    ('Containerize the app', 'Write Dockerfiles for backend and frontend', 'todo');
