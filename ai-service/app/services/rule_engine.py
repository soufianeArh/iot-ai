"""
Turning detections into alerts.

The pipeline so far produces facts. Camera 3 has 730 `person` rows. Every one of
them is true and not one of them is worth a notification - a single person
standing in view for two minutes generates ~40 identical rows at one frame every
three seconds.

This module is the reduction from "what the model saw" to "what a human should
look at", and almost all of it is deduplication. That is the real work in any
alerting system: the condition is easy, not firing 300 times is not.

Three filters, in order:

  1. threshold  - confidence >= rule.min_confidence     (is the model sure?)
  2. quorum     - at least rule.min_count in ONE frame  (is it significant?)
  3. cooldown   - nothing from this rule for N seconds  (have we already said so?)

Cooldown is per (rule, camera), not per rule: two cameras seeing a person are two
different events and must both be reported.

Called from the inference worker thread, inside its app context, right after the
detections are committed.
"""
import logging
import threading

from app import db
from app.models import Alert, AlertRule, utcnow

log = logging.getLogger(__name__)

# Last time each (rule_id, camera_id) pair fired. A cache, not the truth: the
# alert table is the truth. Kept in memory because the check runs on every
# analysed frame and would otherwise be a query per rule per frame.
#
# Guarded by a lock because there is one worker THREAD per camera and they all
# share this dict. A plain dict get/set is atomic in CPython, but the
# check-then-write below is not.
_last_fired: dict[tuple[int, int], object] = {}
_lock = threading.Lock()


class RuleError(Exception):
    """Invalid rule definition."""


# ------------------------------------------------------------------ evaluation

def evaluate(camera_id: int, detections: list, snapshot: str | None) -> list:
    """
    Check one analysed frame against every rule that applies to this camera.

    `detections` are the Detection rows just written for this frame. Returns the
    Alert rows raised, which is usually an empty list - that is the point.
    """
    rules = _rules_for(camera_id)
    if not rules:
        return []

    # Group once. Rules are per label, and a frame with 12 boxes would otherwise
    # be re-scanned for every rule.
    by_label: dict[str, list] = {}
    for detection in detections:
        by_label.setdefault(detection.label, []).append(detection)

    raised = []
    for rule in rules:
        alert = _apply(rule, camera_id, by_label.get(rule.label, []), snapshot)
        if alert is not None:
            raised.append(alert)

    if not raised:
        return []

    db.session.add_all(raised)
    db.session.commit()

    # Only after the commit succeeds. Marking earlier would suppress the next
    # window on the strength of an alert that was never stored.
    now = utcnow()
    with _lock:
        for alert in raised:
            _last_fired[(alert.rule_id, camera_id)] = now

    for alert in raised:
        log.info("ALERT [%s] %s: %s x%s on camera %s (conf %.2f)",
                 alert.severity, alert.rule_name, alert.label,
                 alert.count, camera_id, alert.max_confidence)
    return raised


def _apply(rule: AlertRule, camera_id: int, candidates: list, snapshot: str | None):
    """The three filters. Returns an unsaved Alert, or None."""
    # 1. threshold
    hits = [d for d in candidates if d.confidence >= rule.min_confidence]

    # 2. quorum
    if len(hits) < rule.min_count:
        return None

    # 3. cooldown
    if not _cooldown_expired(rule, camera_id):
        return None

    return Alert(
        rule_id=rule.id,
        rule_name=rule.name,            # snapshot: survives rule deletion
        camera_id=camera_id,
        label=rule.label,
        count=len(hits),
        max_confidence=max(d.confidence for d in hits),
        severity=rule.severity,
        # Prefer the frame the detections came from; they all share one.
        snapshot=snapshot or (hits[0].snapshot if hits else None),
    )


def _rules_for(camera_id: int) -> list:
    """
    Rules that apply to this camera: its own, plus the camera_id IS NULL
    wildcards.

    Queried on every analysed frame rather than cached. At one frame every three
    seconds that is ~0.3 queries/second/camera on an indexed table - far cheaper
    than a cache that has to be invalidated whenever a rule is edited.
    """
    return (AlertRule.query
            .filter(AlertRule.enabled.is_(True))
            .filter(db.or_(AlertRule.camera_id.is_(None),
                           AlertRule.camera_id == camera_id))
            .all())


def _cooldown_expired(rule: AlertRule, camera_id: int) -> bool:
    key = (rule.id, camera_id)

    with _lock:
        last = _last_fired.get(key)

    if last is None:
        # Cold cache - a restart, or the first frame ever for this pair. Fall
        # back to the table, otherwise every service restart would re-announce
        # everything it is still looking at.
        last = (db.session.query(db.func.max(Alert.raised_at))
                .filter(Alert.rule_id == rule.id, Alert.camera_id == camera_id)
                .scalar())
        if last is not None:
            with _lock:
                _last_fired[key] = last

    if last is None:
        return True         # never fired

    return (utcnow() - last).total_seconds() >= rule.cooldown_seconds


def forget(rule_id: int):
    """Drop cached cooldowns for a rule. Called when it is edited or deleted."""
    with _lock:
        for key in [k for k in _last_fired if k[0] == rule_id]:
            del _last_fired[key]


# ------------------------------------------------------------------ validation

def validate(payload: dict, existing: AlertRule | None = None) -> dict:
    """
    Check and normalise a rule from HTTP. Raises RuleError with a message that
    says what to do, not just what is wrong.
    """
    from app.models import SEVERITIES

    def field(name, default):
        return payload.get(name, default)

    name = str(field("name", existing.name if existing else "")).strip()
    if not name:
        raise RuleError("name is required")

    label = str(field("label", existing.label if existing else "")).strip().lower()
    if not label:
        raise RuleError("label is required, e.g. 'person'")

    camera_id = field("cameraId", existing.camera_id if existing else None)
    if camera_id in ("", "any", "null"):
        camera_id = None        # the form sends "" for "any camera"
    if camera_id is not None:
        try:
            camera_id = int(camera_id)
        except (TypeError, ValueError):
            raise RuleError("cameraId must be a number, or omitted for any camera")

    try:
        min_confidence = float(field("minConfidence",
                                     existing.min_confidence if existing else 0.5))
        min_count = int(field("minCount", existing.min_count if existing else 1))
        cooldown = int(field("cooldownSeconds",
                             existing.cooldown_seconds if existing else 60))
    except (TypeError, ValueError):
        raise RuleError("minConfidence, minCount and cooldownSeconds must be numbers")

    if not 0.0 < min_confidence <= 1.0:
        raise RuleError("minConfidence must be between 0 and 1")
    if min_count < 1:
        raise RuleError("minCount must be at least 1")
    if cooldown < 0:
        raise RuleError("cooldownSeconds cannot be negative")

    severity = str(field("severity", existing.severity if existing else "WARNING")).upper()
    if severity not in SEVERITIES:
        raise RuleError(f"severity must be one of {', '.join(SEVERITIES)}")

    enabled = field("enabled", existing.enabled if existing else True)
    if isinstance(enabled, str):
        enabled = enabled.lower() in ("1", "true", "yes", "on")

    return {
        "name": name[:120],
        "camera_id": camera_id,
        "label": label[:64],
        "min_confidence": min_confidence,
        "min_count": min_count,
        "cooldown_seconds": cooldown,
        "severity": severity,
        "enabled": bool(enabled),
    }
