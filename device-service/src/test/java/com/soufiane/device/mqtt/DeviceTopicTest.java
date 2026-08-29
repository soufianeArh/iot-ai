package com.soufiane.device.mqtt;

import org.junit.jupiter.api.Test;

import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;

class DeviceTopicTest {

    @Test
    void parsesAValidTopic() {
        Optional<DeviceTopic> topic = DeviceTopic.parse("iot/pk-test/C001/properties");

        assertThat(topic).isPresent();
        assertThat(topic.get().productKey()).isEqualTo("pk-test");
        assertThat(topic.get().deviceCode()).isEqualTo("C001");
        assertThat(topic.get().action()).isEqualTo("properties");
    }

    @Test
    void parsesStatusTopic() {
        assertThat(DeviceTopic.parse("iot/pk/C001/status"))
                .get()
                .extracting(DeviceTopic::action)
                .isEqualTo("status");
    }

    @Test
    void rejectsWrongPrefix() {
        assertThat(DeviceTopic.parse("other/pk/C001/properties")).isEmpty();
    }

    @Test
    void rejectsTooFewSegments() {
        assertThat(DeviceTopic.parse("iot/pk/C001")).isEmpty();
    }

    @Test
    void rejectsTooManySegments() {
        assertThat(DeviceTopic.parse("iot/pk/C001/properties/extra")).isEmpty();
    }

    @Test
    void rejectsBlankSegment() {
        assertThat(DeviceTopic.parse("iot//C001/properties")).isEmpty();
    }

    @Test
    void rejectsNull() {
        assertThat(DeviceTopic.parse(null)).isEmpty();
    }
}
