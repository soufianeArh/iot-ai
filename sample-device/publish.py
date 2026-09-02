"""
A fake field sensor: temperature, humidity and soil moisture over MQTT.

The device-side mirror of sample-camera. Replace it with a real sensor and
nothing downstream changes - device-service only ever sees a topic and a JSON
payload, and does not know or care what produced them.

WHY THIS IS NOT A SINE WAVE

The first version was, and it looked wrong immediately: six identical humps on
an hour-long chart, every peak the same height to a decimal place. Real traces
never do that, and perfect repetition trains you to read the axis instead of
the data.

So the signal is built from four parts, roughly what a real reading is made of:

  daily cycle  asymmetric - air warms faster after dawn than it cools after
               dusk, so the curve is not a symmetric sine
  weather      a slow mean-reverting random walk, so no two cycles match and
               today differs from yesterday
  events       a passing cloud drops temperature briefly; irrigation lifts
               soil moisture in a step, at an unpredictable moment
  noise        small and independent - the sensor itself

There is still a clear daily shape, so thresholds and alerts stay meaningful,
but nothing lines up on a grid.

It publishes under a productKey/deviceCode that must ALREADY EXIST:
device-service ignores messages from a device it has never been told about,
which is correct and worth seeing rather than papering over.
"""
import json
import logging
import math
import os
import random
import time

import paho.mqtt.client as mqtt

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)-5s %(message)s")
log = logging.getLogger("sample-device")

BROKER = os.getenv("MQTT_HOST", "EMQX")
PORT = int(os.getenv("MQTT_PORT", "1883"))
PRODUCT_KEY = os.getenv("PRODUCT_KEY", "pk-test")
DEVICE_CODE = os.getenv("DEVICE_CODE", "C900")
INTERVAL = float(os.getenv("PUBLISH_INTERVAL_SECONDS", "20"))

# iot/{productKey}/{deviceCode}/{action} - see DeviceTopic.java. A topic that
# does not match this shape is dropped without comment, so it is built from
# the parts rather than written out as one string.
TOPIC = f"iot/{PRODUCT_KEY}/{DEVICE_CODE}/properties"

# A day compressed into DAY_SECONDS. An hour by default: the "last hour" chart
# then shows ONE cycle instead of six copies of the same one, which is most of
# what made the old data look synthetic at a glance.
DAY_SECONDS = float(os.getenv("DAY_SECONDS", "3600"))

# Shifts this device along the cycle, so two sensors are not in lockstep.
PHASE_OFFSET = float(os.getenv("PHASE_OFFSET_SECONDS", "0"))

# Per-device bias, so a greenhouse simply runs warmer than a field.
TEMP_BIAS = float(os.getenv("TEMP_BIAS", "0"))
HUMIDITY_BIAS = float(os.getenv("HUMIDITY_BIAS", "0"))

# Each device gets its own random stream, seeded from its code. Two containers
# started in the same second would otherwise seed identically and generate the
# same "random" weather - which is the duplicate-looking data this exists to
# avoid.
rng = random.Random(f"{PRODUCT_KEY}/{DEVICE_CODE}")


class Sensor:
    """Holds the state a real sensor's surroundings would have."""

    def __init__(self):
        # Mean-reverting drift - the "weather". Kept between readings, which is
        # the point: independent noise per sample reads as jitter, while a
        # random walk reads as conditions changing.
        self.weather = 0.0
        self.soil = 46.0
        self.cloud = 0.0                # a passing cloud, decaying
        self.last = time.monotonic()

    def _daily(self, elapsed: float) -> float:
        """-1 at coldest, +1 at warmest, asymmetric.

        Raising the sine to a power under 1 steepens the morning rise and
        stretches the evening fall, which is how air temperature behaves. A
        plain sine is symmetric, and that symmetry is one of the things the eye
        reads as artificial.
        """
        phase = ((elapsed + PHASE_OFFSET) % DAY_SECONDS) / DAY_SECONDS
        base = math.sin(2 * math.pi * (phase - 0.25))      # coldest at "dawn"
        return math.copysign(abs(base) ** 0.75, base)

    def read(self, elapsed: float) -> dict:
        now = time.monotonic()
        dt = max(0.0, min(60.0, now - self.last))
        self.last = now

        # Ornstein-Uhlenbeck: pulled back toward zero, nudged randomly. Without
        # the pull it wanders off and the sensor reads 40 degrees by lunchtime.
        self.weather += -0.02 * dt * self.weather + rng.gauss(0, 0.25 * math.sqrt(dt))
        self.weather = max(-4.0, min(4.0, self.weather))

        # Clouds: occasional, brief, worth a couple of degrees.
        if rng.random() < 0.02:
            self.cloud = rng.uniform(1.0, 2.5)
        self.cloud *= 0.85 ** dt

        warmth = self._daily(elapsed)
        temperature = (22.0 + TEMP_BIAS + 6.5 * warmth
                       + self.weather - self.cloud + rng.gauss(0, 0.15))

        # Humidity opposes temperature but not exactly - its own drift term is
        # what stops the two lines being mirror images of each other.
        humidity = (60.0 + HUMIDITY_BIAS - 14.0 * warmth
                    - 1.5 * self.weather + 2.0 * self.cloud + rng.gauss(0, 0.8))

        # Soil dries faster when it is warm, and irrigation is a step change at
        # an unpredictable moment rather than a sawtooth on a fixed period.
        self.soil -= (0.004 + 0.0012 * max(0.0, temperature - 18.0)) * dt
        if self.soil < 32.0 and rng.random() < 0.15:
            self.soil = min(50.0, self.soil + rng.uniform(8.0, 14.0))
            log.info("irrigation -> soil %.1f", self.soil)

        return {
            "temperature": round(temperature, 1),
            "humidity": round(max(5.0, min(100.0, humidity)), 1),
            "soilMoisture": round(max(0.0, self.soil + rng.gauss(0, 0.25)), 1),
        }


def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id=f"sample-device-{DEVICE_CODE}")
    # Reconnect on its own: the broker outlives this process being restarted,
    # and vice versa. Without it a single broker blip ends the publisher.
    client.reconnect_delay_set(min_delay=1, max_delay=30)

    while True:
        try:
            log.info("connecting to %s:%s", BROKER, PORT)
            client.connect(BROKER, PORT, keepalive=60)
            break
        except Exception as exc:
            log.warning("broker not ready (%s), retrying in 5s", exc)
            time.sleep(5)

    client.loop_start()
    log.info("publishing to %s every ~%ss (a day lasts %ss)",
             TOPIC, INTERVAL, DAY_SECONDS)

    sensor = Sensor()
    started = time.monotonic()
    while True:
        payload = sensor.read(time.monotonic() - started)
        info = client.publish(TOPIC, json.dumps(payload), qos=1)
        # QoS 1 means the broker acknowledges; without waiting, a failure here
        # is invisible and the loop cheerfully reports success forever.
        info.wait_for_publish(timeout=10)
        if info.rc == mqtt.MQTT_ERR_SUCCESS:
            log.info("%s -> %s", TOPIC, payload)
        else:
            log.warning("publish failed, rc=%s", info.rc)

        # The cadence wobbles too. Real devices do not publish on a metronome,
        # and a perfectly even x-axis is another thing that reads as fake.
        time.sleep(INTERVAL * rng.uniform(0.85, 1.15))


if __name__ == "__main__":
    main()
