"""
Publishes a moving temperature/humidity signal over MQTT, so the platform has
live data instead of two hand-typed readings.

    pip install paho-mqtt
    python tools/fake_sensor.py --device-code C900 --product-key pk-test

The device must already exist (POST /api/devices) - device-service drops
readings from unknown device codes.
"""
import argparse
import json
import math
import random
import signal
import sys
import time

import paho.mqtt.client as mqtt

running = True


def stop(*_):
    global running
    running = False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--product-key", default="pk-test")
    parser.add_argument("--device-code", default="C900")
    parser.add_argument("--interval", type=float, default=5.0)
    args = parser.parse_args()

    base = f"iot/{args.product_key}/{args.device_code}"
    props_topic = f"{base}/properties"
    status_topic = f"{base}/status"

    client = mqtt.Client(client_id=f"fake-sensor-{args.device_code}")

    # Last Will: if this process dies, the BROKER publishes OFFLINE for us.
    # That is how a platform detects a device that vanished without saying goodbye.
    client.will_set(status_topic, json.dumps({"status": "OFFLINE"}), qos=1, retain=False)

    client.connect(args.host, args.port, keepalive=30)
    client.loop_start()
    client.publish(status_topic, json.dumps({"status": "ONLINE"}), qos=1)
    print(f"publishing to {props_topic} every {args.interval}s - Ctrl+C to stop")

    signal.signal(signal.SIGINT, stop)
    tick = 0
    while running:
        # slow sine + noise, so charts in later phases have a real shape
        temperature = round(22 + 4 * math.sin(tick / 12) + random.uniform(-0.3, 0.3), 2)
        humidity = round(55 + 8 * math.sin(tick / 18 + 1) + random.uniform(-0.5, 0.5), 1)
        payload = {"temperature": temperature, "humidity": humidity,
                   "ts": int(time.time() * 1000)}
        client.publish(props_topic, json.dumps(payload), qos=1)
        print(f"-> {payload}")
        tick += 1
        time.sleep(args.interval)

    client.publish(status_topic, json.dumps({"status": "OFFLINE"}), qos=1)
    client.loop_stop()
    client.disconnect()
    print("stopped")


if __name__ == "__main__":
    sys.exit(main())
