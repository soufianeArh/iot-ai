"""
Detections live in their own `ai` schema.

`public` belongs to device-service (Flyway), `video` to video-service.
One service owns a table; everyone else asks that service.
"""
from datetime import datetime, timezone

from app import db

SCHEMA = "ai"


def utcnow():
    return datetime.now(timezone.utc)


class Detection(db.Model):
    __tablename__ = "detection"
    __table_args__ = {"schema": SCHEMA}

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)

    # Plain integer, not a foreign key: video.camera belongs to another service.
    camera_id = db.Column(db.Integer, nullable=False, index=True)

    label = db.Column(db.String(64), nullable=False)      # "person", "bus", ...
    confidence = db.Column(db.Float, nullable=False)      # 0.0 - 1.0

    # Bounding box in pixels, top-left origin.
    x1 = db.Column(db.Integer, nullable=False)
    y1 = db.Column(db.Integer, nullable=False)
    x2 = db.Column(db.Integer, nullable=False)
    y2 = db.Column(db.Integer, nullable=False)

    # Filename of the annotated frame, served by nginx from a shared volume.
    snapshot = db.Column(db.String(128), nullable=True)

    detected_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "cameraId": self.camera_id,
            "label": self.label,
            "confidence": round(self.confidence, 3),
            "box": [self.x1, self.y1, self.x2, self.y2],
            "snapshotUrl": f"/snapshots/{self.snapshot}" if self.snapshot else None,
            "detectedAt": self.detected_at.isoformat() if self.detected_at else None,
        }


# --------------------------------------------------------------------- alerting
#
# A detection is a FACT:      "a person was in frame at 10:04:12".
# An alert is a JUDGEMENT:    "something happened a human should look at".
#
# The two tables below are that distinction. AlertRule says what counts as worth
# reporting; Alert is what was actually reported.


SEVERITIES = ("INFO", "WARNING", "CRITICAL")


class AlertRule(db.Model):
    """
    One condition, evaluated against every analysed frame.

    Deliberately dumb: a label, a confidence floor, a count and a cooldown. That
    is enough for "someone is in the yard" and it stays readable. Anything
    fancier (zones, dwell time, direction of travel) would slot in here without
    changing the rest of the pipeline.
    """
    __tablename__ = "alert_rule"
    __table_args__ = {"schema": SCHEMA}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(120), nullable=False)

    # NULL = applies to every camera. That is why it is nullable: one
    # "person detected anywhere" rule instead of one row per camera.
    camera_id = db.Column(db.Integer, nullable=True, index=True)

    label = db.Column(db.String(64), nullable=False)          # "person", "bus", ...
    min_confidence = db.Column(db.Float, nullable=False, default=0.5)

    # How many of that label must be in ONE frame.
    # min_count=3 turns "a person" into "a group".
    min_count = db.Column(db.Integer, nullable=False, default=1)

    # The single most important column in this table. See rule_engine.py.
    cooldown_seconds = db.Column(db.Integer, nullable=False, default=60)

    severity = db.Column(db.String(16), nullable=False, default="WARNING")
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "cameraId": self.camera_id,          # null = any camera
            "label": self.label,
            "minConfidence": self.min_confidence,
            "minCount": self.min_count,
            "cooldownSeconds": self.cooldown_seconds,
            "severity": self.severity,
            "enabled": self.enabled,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


class Alert(db.Model):
    """
    Something a rule decided was worth reporting.

    `rule_name` is copied in rather than only joined. Deleting a rule must not
    rewrite history: an alert has to keep saying what it said when it fired.
    Hence ON DELETE SET NULL on the FK plus a snapshot of the name.
    """
    __tablename__ = "alert"
    __table_args__ = {"schema": SCHEMA}

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)

    rule_id = db.Column(db.Integer,
                        db.ForeignKey(f"{SCHEMA}.alert_rule.id", ondelete="SET NULL"),
                        nullable=True, index=True)
    rule_name = db.Column(db.String(120), nullable=False)

    camera_id = db.Column(db.Integer, nullable=False, index=True)
    label = db.Column(db.String(64), nullable=False)
    count = db.Column(db.Integer, nullable=False)             # how many in that frame
    max_confidence = db.Column(db.Float, nullable=False)      # the best of them
    severity = db.Column(db.String(16), nullable=False)

    # The frame that triggered it - the reason a human can judge this in one
    # second instead of walking out to look at the camera.
    snapshot = db.Column(db.String(128), nullable=True)

    raised_at = db.Column(db.DateTime(timezone=True), nullable=False,
                          default=utcnow, index=True)

    acknowledged = db.Column(db.Boolean, nullable=False, default=False, index=True)
    acknowledged_at = db.Column(db.DateTime(timezone=True), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "ruleId": self.rule_id,
            "ruleName": self.rule_name,
            "cameraId": self.camera_id,
            "label": self.label,
            "count": self.count,
            "maxConfidence": round(self.max_confidence, 3),
            "severity": self.severity,
            "snapshotUrl": f"/snapshots/{self.snapshot}" if self.snapshot else None,
            "raisedAt": self.raised_at.isoformat() if self.raised_at else None,
            "acknowledged": self.acknowledged,
            "acknowledgedAt": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
        }
