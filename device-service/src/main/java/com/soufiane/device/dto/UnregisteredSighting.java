package com.soufiane.device.dto;

import java.time.OffsetDateTime;

/**
 * An MQTT message that arrived for a device code the DB does not know, or
 * whose product key does not match what was registered. Nothing is written
 * to the DB for these - see DeviceIngestService.resolveDevice - so without
 * this, the only trace was a log line nobody watches. This is that trace,
 * made visible instead: it tells an operator wiring up new hardware "your
 * firmware has been publishing to a code/key that isn't registered" instead
 * of leaving them to wonder why a device never shows up.
 */
public record UnregisteredSighting(
        String productKey,
        String deviceCode,
        String reason,            // "unknown_device" or "product_key_mismatch"
        int count,
        OffsetDateTime firstSeenAt,
        OffsetDateTime lastSeenAt
) {
}
