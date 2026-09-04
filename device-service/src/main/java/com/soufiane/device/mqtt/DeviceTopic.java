package com.soufiane.device.mqtt;

import java.util.Optional;


public record DeviceTopic(String productKey, String deviceCode, String action) {

    private static final int SEGMENTS = 4;
    private static final String PREFIX = "iot";
    //iot/farmA/sensor07/properties
    // into DeviceTopic(productKey="farmA",deviceCode="sensor07", action="properties")
    public static Optional<DeviceTopic> parse(String topic) {
        if (topic == null) {
            return Optional.empty();
        }
        String[] parts = topic.split("/");
        if (parts.length != SEGMENTS || !PREFIX.equals(parts[0])) {
            return Optional.empty();
        }
        for (String part : parts) {
            if (part.isBlank()) {
                return Optional.empty();
            }
        }
        return Optional.of(new DeviceTopic(parts[1], parts[2], parts[3]));
    }
}
