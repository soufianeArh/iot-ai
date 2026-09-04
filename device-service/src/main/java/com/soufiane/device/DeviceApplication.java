package com.soufiane.device;

import com.soufiane.device.mqtt.MqttProperties;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableScheduling
// registers MqttProperties as bean: CONFIG HOLDE
//const data is from appli.yaml
@EnableConfigurationProperties(MqttProperties.class)
public class DeviceApplication {
    //the spring boot entrypoint
    public static void main(String[] args) {
        SpringApplication.run(DeviceApplication.class, args);
    }
}
