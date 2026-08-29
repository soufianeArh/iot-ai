-- One row per reading (history model).
-- The alternative is a "shadow" table holding only the latest value per device.
-- History is kept here because it is simpler and the latest value can still be
-- derived cheaply with Postgres DISTINCT ON (see DevicePropertyRepository).
CREATE TABLE device_property (
    id            BIGSERIAL    PRIMARY KEY,
    device_id     BIGINT       NOT NULL REFERENCES device (id) ON DELETE CASCADE,
    property_key  VARCHAR(64)  NOT NULL,
    property_value TEXT        NOT NULL,
    recorded_at   TIMESTAMPTZ  NOT NULL
);

-- Serves both queries: latest-per-key (DISTINCT ON) and history-for-one-key.
CREATE INDEX idx_device_property_lookup
    ON device_property (device_id, property_key, recorded_at DESC);
