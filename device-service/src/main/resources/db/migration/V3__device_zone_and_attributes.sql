-- Step 4: a device belongs to at most one zone (a plot, field, greenhouse,
-- whatever part of the farm), plus two free-text attributes.

CREATE TABLE device_zone (
    id          BIGSERIAL     PRIMARY KEY,
    name        VARCHAR(128)  NOT NULL UNIQUE,
    description VARCHAR(500),
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT now()
);

ALTER TABLE device ADD COLUMN description VARCHAR(500);
ALTER TABLE device ADD COLUMN location    VARCHAR(255);
-- SET NULL, not CASCADE: deleting a zone must never delete its devices.
ALTER TABLE device ADD COLUMN zone_id BIGINT REFERENCES device_zone (id) ON DELETE SET NULL;

CREATE INDEX idx_device_zone_id ON device (zone_id);
