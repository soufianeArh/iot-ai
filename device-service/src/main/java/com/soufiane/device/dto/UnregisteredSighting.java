package com.soufiane.device.dto;

import java.time.OffsetDateTime;

public record UnregisteredSighting(
        String productKey,
        String deviceCode,
        String reason,            // "unknown_device" or "product_key_mismatch"
        int count,
        OffsetDateTime firstSeenAt,
        OffsetDateTime lastSeenAt
) {
}
