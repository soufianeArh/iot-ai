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
    the entry point, called from worker.py after detections are saved
    runs each rule against its
    matching detections via _apply(), saves any resulting alerts,
    updates the cooldown cache, logs them, returns the list raised (usually empty).
    """
    rules = _rules_for(camera_id)
    if not rules:
        return []

    # Group once. Rules are per label, and a frame with 12 boxes would otherwise
    # be re-scanned for every rule.
    #
    # Keyed on the LOWERCASED label, because validate() lowercases a rule's
    # label on the way in. That was invisible while every model was COCO, whose
    # class names are already lowercase - the plant-disease model emits
    # "Corn leaf blight", and a rule stored as "corn leaf blight" would have
    # matched nothing, silently, forever.
    by_label: dict[str, list] = {}
    for detection in detections:
        by_label.setdefault((detection.label or "").lower(), []).append(detection)

    raised = []
    for rule in rules:
        alert = _apply(rule, camera_id, by_label.get((rule.label or "").lower(), []),
                       snapshot)
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
    """the actual per-rule logic,
    3 checks in order:
      1. filter detections below the rule's min_confidence,
      2. require at least min_count matching hits (quorum),
      3. check the rule's cooldown hasn't already fired recently
    If all three pass, builds and returns an unsaved Alert object
    """
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
    Fetches every rule that should be checked against this camera's frame
    a DB quer:  run fresh every single time a frame gets analyzed.
    """
    # kind == "detection" only. A device rule has no label so it would match
    # nothing here anyway - but leaving it in the query would still let its
    # cooldown tick on camera frames, which is a genuine wrong answer.
    return (AlertRule.query
            .filter(AlertRule.enabled.is_(True))
            .filter(AlertRule.kind == "detection")
            .filter(db.or_(AlertRule.camera_id.is_(None),
                           AlertRule.camera_id == camera_id))
            .all())


def _cooldown_expired(rule: AlertRule, scope) -> bool:
    """
    _last_fired is the cache — a dict of {(rule.id, scope): last_alert_time}.
  - If there's no record for that key anywhere (not in cache, not in DB either) → nothing has ever fired → cooldown is "expired" by default →

    """
    key = (rule.id, scope)

    with _lock:
        last = _last_fired.get(key)

    if last is None:
        # Cold cache - a restart, or the first frame ever for this pair. Fall
        # back to the table, otherwise every service restart would re-announce
        # everything it is still looking at.
        query = (db.session.query(db.func.max(Alert.raised_at))
                 .filter(Alert.rule_id == rule.id))
        if isinstance(scope, str) and scope.startswith("device:"):
            query = query.filter(Alert.device_code == scope.split(":", 1)[1])
        else:
            query = query.filter(Alert.camera_id == scope)
        last = query.scalar()
        if last is not None:
            with _lock:
                _last_fired[key] = last

    if last is None:
        return True         # never fired

    return (utcnow() - last).total_seconds() >= rule.cooldown_seconds


def _remember_fired(rule_id: int, scope):
    """Record that a rule just fired for a scope, starting its cooldown."""
    with _lock:
        _last_fired[(rule_id, scope)] = utcnow()


def forget(rule_id: int):
    """Drop cached cooldowns for a rule. Called when it is edited or deleted."""
    with _lock:
        for key in [k for k in _last_fired if k[0] == rule_id]:
            del _last_fired[key]


# ------------------------------------------------------------------ validation

def validate(payload: dict, existing: AlertRule | None = None) -> dict:
    """
    This validates and cleans up an alert-rule form before saving it to the DB
    """
    from app.models import SEVERITIES

    def field(name, default):
        return payload.get(name, default)

    name = str(field("name", existing.name if existing else "")).strip()
    if not name:
        raise RuleError("name is required")

    kind = str(field("kind", existing.kind if existing else "detection")).strip().lower()
    if kind not in ("detection", "device"):
        raise RuleError("kind must be 'detection' or 'device'")

    # A device rule has no label and a detection rule has no threshold, so the
    # required fields differ by kind. Checked here rather than with a database
    # constraint: the point is a message naming the box to fill in.
    label = str(field("label", existing.label if existing else "") or "").strip().lower()
    if kind == "detection" and not label:
        raise RuleError("label is required, e.g. 'person'")

    device_code = field("deviceCode", existing.device_code if existing else None)
    device_code = str(device_code).strip() if device_code not in (None, "", "any") else None

    property_key = field("propertyKey", existing.property_key if existing else None)
    property_key = str(property_key).strip() if property_key else None

    operator = str(field("operator", existing.operator if existing else ">") or ">").strip()
    threshold = field("threshold", existing.threshold if existing else None)

    if kind == "device":
        if not property_key:
            raise RuleError("propertyKey is required, e.g. 'temperature'")
        if operator not in (">", "<"):
            raise RuleError("operator must be > or <")
        try:
            threshold = float(threshold)
        except (TypeError, ValueError):
            raise RuleError("threshold must be a number, e.g. 35")
        # The label carries what the alert is ABOUT, so a device alert reads
        # "temperature" in the same column a camera alert reads "person".
        label = property_key.lower()
    else:
        property_key = operator = threshold = device_code = None

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
        "kind": kind,
        "camera_id": camera_id if kind == "detection" else None,
        "device_code": device_code,
        "property_key": property_key,
        "operator": operator,
        "threshold": threshold,
        "label": label[:64],
        "min_confidence": min_confidence,
        "min_count": min_count,
        "cooldown_seconds": cooldown,
        "severity": severity,
        "enabled": bool(enabled),
    }
