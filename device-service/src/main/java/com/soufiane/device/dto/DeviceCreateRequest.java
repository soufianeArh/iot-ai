package com.soufiane.device.dto;

import com.soufiane.device.entity.DeviceStatus;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
//create db target body validator
public record DeviceCreateRequest(

        @NotBlank(message = "name is required")
        @Size(max = 128)
        String name,

        @NotBlank(message = "deviceCode is required")
        @Size(max = 64)
        String deviceCode,

        @NotBlank(message = "productKey is required")
        @Size(max = 64)
        String productKey,

        DeviceStatus status,

        // step 4, all optional
        @Size(max = 500) String description,
        @Size(max = 255) String location,
        Long zoneId
) {
}
