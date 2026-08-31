"""ai-service entrypoint: YOLO inference over camera streams."""
import logging
import os

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
log = logging.getLogger("ai-service")


def _database_url() -> str:
    url = os.getenv("DATABASE_URL", "postgresql://postgres:devpass@localhost:5434/myiot")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


def _init_schema(app: Flask):
    """Create the `ai` schema and its tables. See video-service for the lock rationale."""
    with app.app_context():
        lock_key = 0x41494F54
        try:
            db.session.execute(text("SELECT pg_advisory_lock(:k)"), {"k": lock_key})
            db.session.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))
            db.session.commit()
            db.create_all()
            log.info("schema '%s' ready", SCHEMA)
        finally:
            db.session.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": lock_key})
            db.session.commit()


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = _database_url()
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}
    app.config["JSON_SORT_KEYS"] = False

    db.init_app(app)

    from app.blueprints.analysis import analysis_bp
    app.register_blueprint(analysis_bp, url_prefix="/ai")

    # Phase 8. Same prefix on purpose: /ai/rules and /ai/alerts sit beside
    # /ai/tasks, so nginx needs no new location block.
    from app.blueprints.alerts import alerts_bp
    app.register_blueprint(alerts_bp, url_prefix="/ai")

    # Phase 8b: /ai/chat - tool-calling assistant over the tables above.
    from app.blueprints.chat import chat_bp
    app.register_blueprint(chat_bp, url_prefix="/ai")

    @app.get("/ai/health")
    def health():
        try:
            db.session.execute(text("SELECT 1"))
        except Exception as exc:
            log.error("health check failed: %s", exc)
            return jsonify({"status": "DOWN", "db": "DOWN", "error": str(exc)}), 503

        from app.services import task_manager
        # The model is NOT loaded here: doing so would make the container look
        # unhealthy for the ~10s the weights take to load on first request.
        return jsonify({"status": "UP", "db": "UP", "runningTasks": len(task_manager.list_all())})

    @app.errorhandler(404)
    def not_found(_):
        return jsonify({"status": 404, "error": "Not Found"}), 404

    @app.errorhandler(500)
    def server_error(exc):
        log.exception("unhandled error")
        return jsonify({"status": 500, "error": "Internal Server Error"}), 500

    _init_schema(app)

    # Bring back the tasks that should always be running. Off-thread and
    # best-effort: the registry is in memory, so without this a restart leaves
    # every camera idle and the stack looks healthy while detecting nothing.
    from app.services import autostart
    autostart.run(app)

    log.info("ai-service ready, db=%s", _database_url().split("@")[-1])
    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "7000")), debug=True)
