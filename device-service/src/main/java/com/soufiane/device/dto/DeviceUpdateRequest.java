package com.soufiane.device.dto;

import com.soufiane.device.entity.DeviceStatus;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

public record DeviceUpdateRequest(

        @NotBlank(message = "name is required")
        @Size(max = 128)
        String name,

        @NotBlank(message = "productKey is required")
        @Size(max = 64)
        String productKey,

        @NotNull(message = "status is required")
        DeviceStatus status,

        // optional, null clears the field / unassigns the zone
        @Size(max = 500) String description,
        @Size(max = 255) String location,
        Long zoneId
) {
}
