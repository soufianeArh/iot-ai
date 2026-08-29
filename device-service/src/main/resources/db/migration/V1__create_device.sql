CREATE TABLE device (
    id          BIGSERIAL     PRIMARY KEY,
    name        VARCHAR(128)  NOT NULL,
    device_code VARCHAR(64)   NOT NULL UNIQUE,
    product_key VARCHAR(64)   NOT NULL,
    status      VARCHAR(16)   NOT NULL DEFAULT 'OFFLINE',
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT now()
);

CREATE INDEX idx_device_product_key ON device (product_key);
