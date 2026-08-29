package com.soufiane.device.controller;

import com.soufiane.device.dto.DevicePropertyResponse;
import com.soufiane.device.service.DevicePropertyService;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/devices/{deviceId}/properties")
@Validated
public class DevicePropertyController {

    private final DevicePropertyService devicePropertyService;

    public DevicePropertyController(DevicePropertyService devicePropertyService) {
        this.devicePropertyService = devicePropertyService;
    }

    /**
     * No `key` -> latest value of every property.
     * With `key` -> most recent readings of that one property.
     */
    @GetMapping
    public List<DevicePropertyResponse> read(
            @PathVariable Long deviceId,
            @RequestParam(required = false) String key,
            @RequestParam(defaultValue = "50") @Min(1) @Max(500) int limit) {

        return (key == null || key.isBlank())
                ? devicePropertyService.latest(deviceId)
                : devicePropertyService.history(deviceId, key, limit);
    }
}
