package com.soufiane.device.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.soufiane.device.dto.UnregisteredSighting;
import com.soufiane.device.entity.Device;
import com.soufiane.device.entity.DeviceProperty;
import com.soufiane.device.entity.DeviceStatus;
import com.soufiane.device.mqtt.DeviceTopic;
import com.soufiane.device.repository.DevicePropertyRepository;
import com.soufiane.device.repository.DeviceRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Turns raw MQTT messages into rows. Every failure path here logs and returns:
 * a bad payload from one device must never break the subscriber loop.
 */
@Service
//turns mqtt messages into rows in db
public class DeviceIngestService {

    private static final Logger log = LoggerFactory.getLogger(DeviceIngestService.class);
    //JSON key a device is expected to use for its own timestamp, e.g. {"ts": 1699999999000, temp
    private static final String TIMESTAMP_FIELD = "ts";

    //Device sends bad MQTT message → MqttSubscriber
    //→ DeviceIngestService.handleProperties()
    //→ resolveDevice() fails → recordUnregistered() → adds one line to the in-memory Map
    private static final int MAX_TRACKED_UNREGISTERED = 200;

    private final DeviceRepository deviceRepository;
    private final DevicePropertyRepository devicePropertyRepository;
    private final ObjectMapper objectMapper;
    private final Map<String, UnregisteredSighting> unregisteredSightings = new ConcurrentHashMap<>();

    public DeviceIngestService(DeviceRepository deviceRepository,
                               DevicePropertyRepository devicePropertyRepository,
                               ObjectMapper objectMapper) {
        this.deviceRepository = deviceRepository;
        this.devicePropertyRepository = devicePropertyRepository;
        this.objectMapper = objectMapper;
    }

    @Transactional
    public void handleProperties(String topic, String payload) {
        Optional<Device> maybeDevice = resolveDevice(topic);
        if (maybeDevice.isEmpty()) {
            return;
        }
        Device device = maybeDevice.get();

        JsonNode root;
        try {
            root = objectMapper.readTree(payload);
        } catch (Exception e) {
            log.warn("MQTT {}: malformed JSON payload, dropped ({})", topic, e.getMessage());
            return;
        }
        if (!root.isObject()) {
            log.warn("MQTT {}: payload is not a JSON object, dropped", topic);
            return;
        }

        OffsetDateTime recordedAt = readTimestamp(root);
        List<DeviceProperty> batch = new ArrayList<>();

        for (Iterator<Map.Entry<String, JsonNode>> it = root.fields(); it.hasNext(); ) {
            Map.Entry<String, JsonNode> field = it.next();
            String key = field.getKey();
            JsonNode value = field.getValue();

            if (TIMESTAMP_FIELD.equals(key)) {
                continue;
            }
            if (!value.isValueNode() || value.isNull()) {
                log.debug("MQTT {}: skipping non-scalar property '{}'", topic, key);
                continue;
            }
            batch.add(new DeviceProperty(device.getId(), key, value.asText(), recordedAt));
        }

        if (batch.isEmpty()) {
            log.warn("MQTT {}: no usable properties in payload", topic);
            return;
        }
        devicePropertyRepository.saveAll(batch);

        // any report proves the device is alive
        if (device.getStatus() != DeviceStatus.ONLINE) {
            device.setStatus(DeviceStatus.ONLINE);
        }
        log.info("MQTT {}: stored {} properties for device {}", topic, batch.size(), device.getDeviceCode());
    }

    @Transactional
    public void handleStatus(String topic, String payload) {
        Optional<Device> maybeDevice = resolveDevice(topic);
        if (maybeDevice.isEmpty()) {
            return;
        }
        Device device = maybeDevice.get();

        String raw = payload == null ? "" : payload.trim();
        // accept either {"status":"ONLINE"} or a bare ONLINE / offline
        if (raw.startsWith("{")) {
            try {
                JsonNode node = objectMapper.readTree(raw).path("status");
                raw = node.isMissingNode() ? "" : node.asText("");
            } catch (Exception e) {
                log.warn("MQTT {}: malformed status payload, dropped", topic);
                return;
            }
        }

        DeviceStatus status;
        try {
            status = DeviceStatus.valueOf(raw.toUpperCase());
        } catch (IllegalArgumentException e) {
            log.warn("MQTT {}: unknown status '{}', expected ONLINE or OFFLINE", topic, raw);
            return;
        }

        device.setStatus(status);
        log.info("MQTT {}: device {} is now {}", topic, device.getDeviceCode(), status);
    }
    // case resolved: pg repo append
    //no resolve: unregiteerd device in RAM 200limit
    private Optional<Device> resolveDevice(String topic) {
        Optional<DeviceTopic> parsed = DeviceTopic.parse(topic);
        if (parsed.isEmpty()) {
            log.warn("MQTT {}: unparseable topic, dropped", topic);
            return Optional.empty();
        }
        DeviceTopic deviceTopic = parsed.get();

        Optional<Device> device = deviceRepository.findByDeviceCode(deviceTopic.deviceCode());
        //device code not found >> unregistered list
        if (device.isEmpty()) {
            log.warn("MQTT {}: unknown deviceCode '{}', dropped", topic, deviceTopic.deviceCode());
            recordUnregistered(deviceTopic.productKey(), deviceTopic.deviceCode(), "unknown_device");
            return Optional.empty();
        }
        //device code is registered >> unregistered
        if (!device.get().getProductKey().equals(deviceTopic.productKey())) {
            log.warn("MQTT {}: productKey mismatch (topic='{}', registered='{}'), dropped",
                    topic, deviceTopic.productKey(), device.get().getProductKey());
            recordUnregistered(deviceTopic.productKey(), deviceTopic.deviceCode(), "product_key_mismatch");
            return Optional.empty();
        }
        return device;
    }
    //productKey, deviceCode, reason, count, firstSeenAt, lastSeenAt.
    // That's it. No sensor data, no property values
    //same unregisterd : updates the value + count in ram (no new ram record)
    private void recordUnregistered(String productKey, String deviceCode, String reason) {
        String key = productKey + "/" + deviceCode;
        OffsetDateTime now = OffsetDateTime.now(ZoneOffset.UTC);
        unregisteredSightings.compute(key, (k, existing) -> existing == null
                ? new UnregisteredSighting(productKey, deviceCode, reason, 1, now, now)
                : new UnregisteredSighting(productKey, deviceCode, reason,
                        existing.count() + 1, existing.firstSeenAt(), now));

        if (unregisteredSightings.size() > MAX_TRACKED_UNREGISTERED) {
            unregisteredSightings.entrySet().stream()
                    .min(Comparator.comparing(e -> e.getValue().lastSeenAt()))
                    .ifPresent(e -> unregisteredSightings.remove(e.getKey()));
        }
    }

    //display the unregisted devices
    //timestamp sort
    public List<UnregisteredSighting> listUnregistered() {
        return unregisteredSightings.values().stream()
                .sorted(Comparator.comparing(UnregisteredSighting::lastSeenAt).reversed())
                .toList();
    }

    private OffsetDateTime readTimestamp(JsonNode root) {
        JsonNode ts = root.path(TIMESTAMP_FIELD);
        if (ts.isNumber()) {
            return OffsetDateTime.ofInstant(Instant.ofEpochMilli(ts.asLong()), ZoneOffset.UTC);
        }
        return OffsetDateTime.now(ZoneOffset.UTC);
    }
}
