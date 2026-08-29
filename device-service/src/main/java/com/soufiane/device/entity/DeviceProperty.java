package com.soufiane.device.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.time.OffsetDateTime;

/**
 * A single reading reported by a device over MQTT.
 *
 * device_id is a plain column rather than a @ManyToOne association: the ingest path
 * already resolved the Device, so an association would only add lazy-loading overhead
 * on the hottest write path in the service.
 */
@Entity
@Table(name = "device_property")
public class DeviceProperty {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "device_id", nullable = false)
    private Long deviceId;

    @Column(name = "property_key", nullable = false, length = 64)
    private String propertyKey;

    @Column(name = "property_value", nullable = false, columnDefinition = "text")
    private String propertyValue;

    @Column(name = "recorded_at", nullable = false)
    private OffsetDateTime recordedAt;

    protected DeviceProperty() {
        // required by JPA
    }

    public DeviceProperty(Long deviceId, String propertyKey, String propertyValue, OffsetDateTime recordedAt) {
        this.deviceId = deviceId;
        this.propertyKey = propertyKey;
        this.propertyValue = propertyValue;
        this.recordedAt = recordedAt;
    }

    public Long getId() {
        return id;
    }

    public Long getDeviceId() {
        return deviceId;
    }

    public String getPropertyKey() {
        return propertyKey;
    }

    public String getPropertyValue() {
        return propertyValue;
    }

    public OffsetDateTime getRecordedAt() {
        return recordedAt;
    }
}
