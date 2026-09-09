CREATE TABLE app_user (
    id            BIGSERIAL     PRIMARY KEY,
    username      VARCHAR(64)   NOT NULL UNIQUE,
    password_hash VARCHAR(100)  NOT NULL,
    display_name  VARCHAR(128)  NOT NULL,
    role          VARCHAR(32)   NOT NULL DEFAULT 'ADMIN',
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT now()
);

-- Seeded so there's a way in on first boot, no register endpoint exists.
-- username admin, password changeme123, change it via PUT /api/auth/me
-- right after first login.
INSERT INTO app_user (username, password_hash, display_name, role)
VALUES ('admin', '$2b$10$kWDolsIxXdF6f6THAmSkneBuPQwcLoIx8GGIPXigDgsaT4Mv.iXOi', 'Admin', 'ADMIN');
