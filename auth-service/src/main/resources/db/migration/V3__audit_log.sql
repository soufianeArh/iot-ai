-- Step 5: one row per mutating request across the whole stack. Every
-- service ships its writes here (auth-service writes directly, the others
-- POST to /internal/audit). Reads are never recorded.
CREATE TABLE audit_log (
    id          BIGSERIAL     PRIMARY KEY,
    at          TIMESTAMPTZ   NOT NULL DEFAULT now(),
    actor       VARCHAR(64),
    actor_role  VARCHAR(16),
    service     VARCHAR(32)   NOT NULL,
    method      VARCHAR(8)    NOT NULL,
    action      VARCHAR(16)   NOT NULL,
    resource    VARCHAR(32),
    resource_id VARCHAR(64),
    path        VARCHAR(255)  NOT NULL,
    status      SMALLINT      NOT NULL,
    outcome     VARCHAR(16)   NOT NULL,
    ip          VARCHAR(45)
);

CREATE INDEX idx_audit_log_at ON audit_log (at DESC);
CREATE INDEX idx_audit_log_actor ON audit_log (actor);
CREATE INDEX idx_audit_log_resource ON audit_log (resource, resource_id);
