package com.soufiane.device.dto;

import com.soufiane.device.entity.DeviceZone;

import java.time.OffsetDateTime;

public record ZoneResponse(
        Long id,
        String name,
        String description,
        long deviceCount,
        OffsetDateTime createdAt
) {
    public static ZoneResponse from(DeviceZone zone, long deviceCount) {
        return new ZoneResponse(zone.getId(), zone.getName(), zone.getDescription(),
                deviceCount, zone.getCreatedAt());
    }
}
