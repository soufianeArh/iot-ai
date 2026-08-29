package com.soufiane.device.dto;

import com.soufiane.device.entity.DeviceProperty;

import java.time.OffsetDateTime;

public record DevicePropertyResponse(
        String key,
        String value,
        OffsetDateTime recordedAt
) {
    public static DevicePropertyResponse from(DeviceProperty p) {
        return new DevicePropertyResponse(p.getPropertyKey(), p.getPropertyValue(), p.getRecordedAt());
    }
}
