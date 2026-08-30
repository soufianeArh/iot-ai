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
