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
        OffsetDateTime createdAt
) {
    public static DeviceResponse from(Device device) {
        return new DeviceResponse(
                device.getId(),
                device.getName(),
                device.getDeviceCode(),
                device.getProductKey(),
                device.getStatus(),
                device.getCreatedAt()
        );
    }
}
