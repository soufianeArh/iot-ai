
import logging
import os
import time

from dotenv import load_dotenv
from flask import Flask, jsonify
from sqlalchemy import text

from app import db
from app.models import SCHEMA

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
)
log = logging.getLogger("video-service")

# read the db url from different ENV
def _database_url() -> str:
    url = os.getenv("DATABASE_URL", "postgresql://postgres:devpass@localhost:5434/myiot")
    # SQLAlchemy 2.x rejects the legacy postgres:// prefix
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url

"""
creates video tables and createall() initil db
wrapped in a Postgres advisory lock so multiple gunicorn workers
booting in parallel don't race each other into creating the schema twice.
"""
def _init_schema(app: Flask):
    """
    Create the `video` schema, then the tables inside it.

    create_all() is safe here because this service is the sole owner of the
    `video` schema. It is NOT a substitute for migrations: the moment a column
    needs changing, this must become Alembic. create_all() only ever adds
    missing tables, it never alters existing ones.
    """
    with app.app_context():
        # A Postgres advisory lock serialises this across gunicorn workers.
        # Without it, "CREATE SCHEMA IF NOT EXISTS" is NOT atomic: two workers
        # both see the schema missing, both try to create it, and the loser dies
        # with UniqueViolation on pg_namespace. Same race applies to create_all().
        lock_key = 0x5645444F  # arbitrary constant, shared by every worker
        try:
            db.session.execute(text("SELECT pg_advisory_lock(:k)"), {"k": lock_key})
            db.session.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))
            db.session.commit()
            db.create_all()
            log.info("schema '%s' ready", SCHEMA)
        finally:
            db.session.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": lock_key})
            db.session.commit()


def _resync_streams(app: Flask):
    """
    Rebuild the media server's camera list from the database at startup.

    MediaMTX loses every API-added path when it restarts, so without this a
    restart leaves cameras that exist in Postgres but cannot be played.
    BestEffort: video-service must still start if the media server is down, and it
    retries because MediaMTX may not be accepting connections yet.
    """
    from app.services import camera_service

    with app.app_context():
        for attempt in range(1, 4):
            try:
                camera_service.resync_streams()
                return
            except Exception as exc:
                log.warning("stream resync attempt %s failed: %s", attempt, exc)
                time.sleep(3)
        log.error("stream resync gave up; use POST /video/camera/<id>/stream to restore")


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = _database_url()
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}
    app.config["JSON_SORT_KEYS"] = False

    """
      from flask_sqlalchemy import SQLAlchemy
      app.config is config container ONLY
    """
    db.init_app(app)

    from app.blueprints.camera import camera_bp
    app.register_blueprint(camera_bp, url_prefix="/video/camera")

    @app.get("/video/health")
    def health():
        try:
            db.session.execute(text("SELECT 1"))
            return jsonify({"status": "UP", "db": "UP"})
        except Exception as exc:
            log.error("health check failed: %s", exc)
            return jsonify({"status": "DOWN", "db": "DOWN", "error": str(exc)}), 503

    @app.errorhandler(404)
    def not_found(_):
        return jsonify({"status": 404, "error": "Not Found"}), 404

    @app.errorhandler(500)
    def server_error(exc):
        log.exception("unhandled error")
        return jsonify({"status": 500, "error": "Internal Server Error"}), 500

    _init_schema(app)
    _resync_streams(app)
    log.info("video-service ready, db=%s", _database_url().split("@")[-1])
    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "6000")), debug=True)
