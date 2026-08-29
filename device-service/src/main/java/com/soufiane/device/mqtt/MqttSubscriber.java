package com.soufiane.device.mqtt;

import com.soufiane.device.service.DeviceIngestService;
import jakarta.annotation.PreDestroy;
import org.eclipse.paho.client.mqttv3.IMqttDeliveryToken;
import org.eclipse.paho.client.mqttv3.MqttCallbackExtended;
import org.eclipse.paho.client.mqttv3.MqttClient;
import org.eclipse.paho.client.mqttv3.MqttConnectOptions;
import org.eclipse.paho.client.mqttv3.MqttMessage;
import org.eclipse.paho.client.mqttv3.persist.MemoryPersistence;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.nio.charset.StandardCharsets;
import java.util.UUID;

/**
 * Owns the MQTT connection and routes inbound messages to {@link DeviceIngestService}.
 *
 * Paho's automatic reconnect only kicks in AFTER one successful connect, so the
 * scheduled ensureConnected() covers the case where the broker is not up yet at
 * startup. The service must boot even with no broker present.
 */
@Component
public class MqttSubscriber implements MqttCallbackExtended {

    private static final Logger log = LoggerFactory.getLogger(MqttSubscriber.class);

    private final MqttProperties properties;
    private final DeviceIngestService ingestService;
    private final MqttClient client;

    public MqttSubscriber(MqttProperties properties, DeviceIngestService ingestService) throws Exception {
        this.properties = properties;
        this.ingestService = ingestService;
        // client id must be unique per connection, else the broker kicks the older one
        String clientId = properties.getClientId() + "-" + UUID.randomUUID().toString().substring(0, 8);
        this.client = new MqttClient(properties.getBrokerUrl(), clientId, new MemoryPersistence());
        this.client.setCallback(this);
    }

    @Scheduled(initialDelay = 2000, fixedDelay = 10000)
    public void ensureConnected() {
        if (client.isConnected()) {
            return;
        }
        try {
            MqttConnectOptions options = new MqttConnectOptions();
            options.setAutomaticReconnect(true);
            options.setCleanSession(true);
            options.setConnectionTimeout(10);
            options.setKeepAliveInterval(30);
            if (properties.getUsername() != null && !properties.getUsername().isBlank()) {
                options.setUserName(properties.getUsername());
                options.setPassword(properties.getPassword() == null
                        ? new char[0] : properties.getPassword().toCharArray());
            }
            client.connect(options);
            log.info("MQTT connected to {}", properties.getBrokerUrl());
        } catch (Exception e) {
            log.warn("MQTT connect to {} failed, retrying in 10s ({})",
                    properties.getBrokerUrl(), e.getMessage());
        }
    }

    /** Fires on first connect AND on every automatic reconnect - so resubscribe here. */
    @Override
    public void connectComplete(boolean reconnect, String serverUri) {
        try {
            client.subscribe(properties.getPropertiesTopic(), properties.getQos());
            client.subscribe(properties.getStatusTopic(), properties.getQos());
            log.info("MQTT subscribed to '{}' and '{}' (reconnect={})",
                    properties.getPropertiesTopic(), properties.getStatusTopic(), reconnect);
        } catch (Exception e) {
            log.error("MQTT subscribe failed", e);
        }
    }

    @Override
    public void messageArrived(String topic, MqttMessage message) {
        String payload = new String(message.getPayload(), StandardCharsets.UTF_8);
        log.debug("MQTT <- {} : {}", topic, payload);
        try {
            if (topic.endsWith("/status")) {
                ingestService.handleStatus(topic, payload);
            } else {
                ingestService.handleProperties(topic, payload);
            }
        } catch (Exception e) {
            // never let one bad message kill the subscriber loop
            log.error("MQTT {}: handler threw, message dropped", topic, e);
        }
    }

    @Override
    public void connectionLost(Throwable cause) {
        log.warn("MQTT connection lost: {}", cause == null ? "unknown" : cause.getMessage());
    }

    @Override
    public void deliveryComplete(IMqttDeliveryToken token) {
        // publisher-side callback; unused
    }

    @PreDestroy
    public void shutdown() {
        try {
            if (client.isConnected()) {
                client.disconnect();
            }
            client.close();
        } catch (Exception e) {
            log.debug("MQTT shutdown: {}", e.getMessage());
        }
    }
}
