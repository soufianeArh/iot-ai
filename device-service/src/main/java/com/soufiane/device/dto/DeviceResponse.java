package com.soufiane.device.dto;

import com.soufiane.device.entity.Device;
import com.soufiane.device.entity.DeviceStatus;

import java.time.OffsetDateTime;

public record DeviceResponse(
        Long id,
        String name,
        String deviceCode,
        String productKey,
        DeviceStatus status,
        String description,
        String location,
        Long zoneId,
        String zoneName,
        OffsetDateTime createdAt
) {
    public static DeviceResponse from(Device device) {
        return from(device, null);
    }

    // zoneName resolved by the caller from a single zone lookup, so a device
    // list isn't one join per row.
    public static DeviceResponse from(Device device, String zoneName) {
        return new DeviceResponse(
                device.getId(),
                device.getName(),
                device.getDeviceCode(),
                device.getProductKey(),
                device.getStatus(),
                device.getDescription(),
                device.getLocation(),
                device.getZoneId(),
                zoneName,
                device.getCreatedAt()
        );
    }
}
