"""
SQLAlchemy models for video-service.

Every table lives in the `video` schema, NOT `public`. `public` belongs to
device-service, whose Flyway migrations run with hibernate ddl-auto=validate:
two services creating tables in one schema is how silent conflicts start.
One service owns a table; everyone else asks that service over HTTP.
"""
from datetime import datetime, timezone

from app import db

SCHEMA = "video"


def utcnow():
    return datetime.now(timezone.utc)


class Camera(db.Model):
    __tablename__ = "camera"
    __table_args__ = {"schema": SCHEMA}

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    name = db.Column(db.String(128), nullable=False)
    rtsp_url = db.Column(db.Text, nullable=False)

    # Plain string, not a foreign key: the `device` table is in another schema
    # owned by another service. Existence is checked over HTTP at write time.
    device_code = db.Column(db.String(64), nullable=True)

    # Filled in by ffprobe at registration time.
    status = db.Column(db.String(16), nullable=False, default="UNKNOWN")
    codec = db.Column(db.String(32), nullable=True)
    width = db.Column(db.Integer, nullable=True)
    height = db.Column(db.Integer, nullable=True)
    fps = db.Column(db.Float, nullable=True)
    last_error = db.Column(db.Text, nullable=True)
    last_probed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "rtspUrl": self.rtsp_url,
            "deviceCode": self.device_code,
            "status": self.status,
            "codec": self.codec,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "lastError": self.last_error,
            "lastProbedAt": self.last_probed_at.isoformat() if self.last_probed_at else None,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }
