"""
Verifies the JWT auth-service issues, either a real user's (from a browser,
via nginx) or a service token (from ai-service calling this directly,
service to service, over the private docker network).

Signed HS512 with the same JWT_SECRET as auth-service. Java's
Keys.hmacShaKeyFor() picks HS512 for a key this long, so this has to match
that exactly, not HS256, or every real token fails to verify here.
"""
import logging
import os

import jwt
from flask import jsonify, request

log = logging.getLogger(__name__)

JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-secret-change-me-before-anything-real-CHANGE-ME")

# Docker's healthcheck has no token to send, same reasoning as nginx's own
# /healthz bypass.
EXEMPT_PATHS = {"/video/health"}


def verify(token: str) -> dict | None:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS512"])
    except jwt.PyJWTError as exc:
        log.debug("token rejected: %s", exc)
        return None


def install(app):
    @app.before_request
    def _require_auth():
        if request.path in EXEMPT_PATHS:
            return None

        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return jsonify({"status": 401, "error": "Unauthorized", "message": "authentication required"}), 401

        claims = verify(header[len("Bearer "):])
        if claims is None:
            return jsonify({"status": 401, "error": "Unauthorized", "message": "invalid or expired token"}), 401

        # Any authenticated role can read. A write needs ADMIN or OPERATOR,
        # a VIEWER token stops here. SERVICE (ai-service calling directly)
        # is trusted regardless of method, it's not a human role.
        #
        # POST .../stream is the one exception: that's what "Watch" sends to
        # start playback, a write in method only, watching is a VIEWER
        # capability. DELETE .../stream stops the shared stream for everyone
        # currently watching it, that stays a real write.
        is_watch_start = request.method == "POST" and request.path.endswith("/stream")
        if request.method in ("GET", "HEAD", "OPTIONS") or is_watch_start:
            return None
        if claims.get("role") not in ("ADMIN", "OPERATOR", "SERVICE"):
            return jsonify({"status": 403, "error": "Forbidden", "message": "you do not have permission for this action"}), 403

        return None
