"""
Device threshold rules: alert when a sensor reading crosses a limit.

WHY THIS POLLS RATHER THAN SUBSCRIBING

The obvious design is to evaluate on the MQTT ingest path, in device-service,
the moment a reading arrives. It was not done that way because alerts live in
the `ai` schema and device-service owns `device` - having a Java service write
rows into the Python service's tables couples them at the database, which is
the coupling hardest to undo later.

The alternative, an MQTT subscription here, is genuinely event-driven but adds
a broker client, a second consumer group and a reconnection story to a service
whose job is inference.

So: ai-service polls device-service over HTTP, which it already does for the
chat tools. The cost is latency - up to POLL_SECONDS between a reading and its
alert. For "the greenhouse is too hot" that is the right trade; for anything
needing sub-second reaction it would not be, and the honest fix then is the
MQTT subscription, not a faster poll.

Cooldown, severity and acknowledgement are shared with detection rules,
because from the operator's side an alert is an alert.
"""
import logging
import os
import threading
import time

import requests

from app import db
from app.models import Alert, AlertRule
from app.services.rule_engine import _cooldown_expired, _remember_fired

log = logging.getLogger(__name__)

DEVICE_SERVICE_URL = os.getenv("DEVICE_SERVICE_URL", "http://device-service:8080")
POLL_SECONDS = float(os.getenv("DEVICE_RULE_POLL_SECONDS", "15"))
TIMEOUT = 8

ENABLED = os.getenv("DEVICE_RULES_ENABLED", "true").lower() in ("1", "true", "yes")


def _devices() -> list:
    r = requests.get(f"{DEVICE_SERVICE_URL}/api/devices", timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def _properties(device_id: int) -> list:
    r = requests.get(f"{DEVICE_SERVICE_URL}/api/devices/{device_id}/properties",
                     timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def _breaches(rule, value: float) -> bool:
    return value > rule.threshold if rule.operator == ">" else value < rule.threshold


def evaluate_once() -> list:
    """One pass over every device rule. Returns the alerts raised."""
    rules = (AlertRule.query
             .filter(AlertRule.enabled.is_(True))
             .filter(AlertRule.kind == "device")
             .all())
    if not rules:
        return []

    # Fetched once per pass, not once per rule: ten rules over three devices
    # would otherwise be thirty HTTP calls every POLL_SECONDS.
    readings = {}                       # deviceCode -> {property: (value, name)}
    for device in _devices():
        code = device.get("deviceCode")
        if not code:
            continue
        values = {}
        for prop in _properties(device["id"]):
            try:
                values[str(prop.get("key", "")).lower()] = float(prop.get("value"))
            except (TypeError, ValueError):
                # A non-numeric property is normal - a firmware string, a mode.
                # It simply cannot be compared against a threshold.
                continue
        readings[code] = (values, device.get("name") or code)

    raised = []
    for rule in rules:
        key = (rule.property_key or "").lower()
        # device_code NULL means "any device reporting this property", which is
        # what you want for a site-wide "anything over 35" rule.
        targets = ([rule.device_code] if rule.device_code
                   else list(readings))

        for code in targets:
            entry = readings.get(code)
            if not entry:
                continue
            values, _name = entry
            if key not in values or not _breaches(rule, values[key]):
                continue
            # Cooldown is keyed on the DEVICE, not the rule alone: one rule
            # across ten sensors must be able to alert about each of them.
            if not _cooldown_expired(rule, f"device:{code}"):
                continue

            raised.append(Alert(
                rule_id=rule.id,
                rule_name=rule.name,
                camera_id=None,
                device_code=code,
                label=key,
                count=1,
                max_confidence=values[key],   # the reading; see models.py
                severity=rule.severity,
                snapshot=None,
            ))

    if not raised:
        return []

    db.session.add_all(raised)
    db.session.commit()
    for alert in raised:
        _remember_fired(alert.rule_id, f"device:{alert.device_code}")
        log.info("ALERT [%s] %s: %s %s %s on %s (read %s)",
                 alert.severity, alert.rule_name, alert.label,
                 next((r.operator for r in rules if r.id == alert.rule_id), "?"),
                 next((r.threshold for r in rules if r.id == alert.rule_id), "?"),
                 alert.device_code, alert.max_confidence)
    return raised


def run(app):
    """Start the poller. Returns immediately; work happens off-thread."""
    if not ENABLED:
        log.info("device rules disabled")
        return

    def worker():
        log.info("device rule poller started (every %ss)", POLL_SECONDS)
        while True:
            time.sleep(POLL_SECONDS)
            try:
                with app.app_context():
                    evaluate_once()
            except requests.RequestException as exc:
                # device-service restarting is normal and not worth a stack
                # trace every 15 seconds.
                log.debug("device rules: device-service unreachable (%s)", exc)
            except Exception:
                log.exception("device rule evaluation failed")
                try:
                    with app.app_context():
                        db.session.rollback()
                except Exception:
                    pass

    threading.Thread(target=worker, name="device-rules", daemon=True).start()
