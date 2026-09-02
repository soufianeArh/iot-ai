# A fake IoT device: publishes plausible sensor readings over MQTT on a loop.
#
# The mirror of sample-camera. That one gives YOLO something to look at; this
# gives the MQTT ingest path something to carry, so the devices page shows
# moving data instead of values frozen at whenever someone last published by
# hand.
FROM python:3.12-slim

RUN pip install --no-cache-dir paho-mqtt==2.1.0

WORKDIR /app
COPY publish.py /app/publish.py

ENTRYPOINT ["python", "-u", "/app/publish.py"]
