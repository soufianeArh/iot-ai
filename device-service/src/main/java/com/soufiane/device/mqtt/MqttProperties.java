package com.soufiane.device.mqtt;

import org.springframework.boot.context.properties.ConfigurationProperties;

//@ConfigurationProperties(prefix="mqtt") at boot
// gets config from application.yml
@ConfigurationProperties(prefix = "mqtt")
public class MqttProperties {

    /** e.g. tcp://emqx:1883 */
    private String brokerUrl = "tcp://localhost:1883";
    private String clientId = "device-service";
    private String username;
    private String password;

    /** iot/{productKey}/{deviceCode}/properties */
    private String propertiesTopic = "iot/+/+/properties";
    /** iot/{productKey}/{deviceCode}/status */
    private String statusTopic = "iot/+/+/status";

    private int qos = 1;

    public String getBrokerUrl() { return brokerUrl; }
    public void setBrokerUrl(String brokerUrl) { this.brokerUrl = brokerUrl; }

    public String getClientId() { return clientId; }
    public void setClientId(String clientId) { this.clientId = clientId; }

    public String getUsername() { return username; }
    public void setUsername(String username) { this.username = username; }

    public String getPassword() { return password; }
    public void setPassword(String password) { this.password = password; }

    public String getPropertiesTopic() { return propertiesTopic; }
    public void setPropertiesTopic(String propertiesTopic) { this.propertiesTopic = propertiesTopic; }

    public String getStatusTopic() { return statusTopic; }
    public void setStatusTopic(String statusTopic) { this.statusTopic = statusTopic; }

    public int getQos() { return qos; }
    public void setQos(int qos) { this.qos = qos; }
}
