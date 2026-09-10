"""
Two jobs: verify the JWT auth-service issues on every incoming request, and
mint a short lived service token for the outbound calls this service makes
to video-service and device-service, since those are ai-service calling
another backend directly, not a logged in user, and have no user token to
forward.

Signed HS512 with the same JWT_SECRET as auth-service, same reasoning as
video-service's app/auth.py.
"""
import logging
import os
import time

import jwt
from flask import jsonify, request

log = logging.getLogger(__name__)

JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-secret-change-me-before-anything-real-CHANGE-ME")

EXEMPT_PATHS = {"/ai/health"}

# POST, but reads only, never changes anything, so it's treated as a read
# for the role gate below rather than requiring ADMIN/OPERATOR like a normal write.
READ_EQUIVALENT_PATHS = {"/ai/chat"}

SERVICE_TOKEN_TTL_SECONDS = 300


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
        # a VIEWER token stops here. SERVICE (ai-service's own outbound
        # calls, not used inbound today but kept consistent) is trusted
        # regardless of method, it's not a human role.
        if request.method in ("GET", "HEAD", "OPTIONS") or request.path in READ_EQUIVALENT_PATHS:
            return None
        if claims.get("role") not in ("ADMIN", "OPERATOR", "SERVICE"):
            return jsonify({"status": 403, "error": "Forbidden", "message": "you do not have permission for this action"}), 403

        return None


def service_headers() -> dict:
    """Authorization header for a call this service makes to another one.

    Minted fresh per call rather than cached: encoding a JWT is cheap, and it
    avoids a whole class of "cached token expired mid-flight" bugs.
    """
    now = int(time.time())
    token = jwt.encode(
        {"sub": "ai-service", "role": "SERVICE", "iat": now, "exp": now + SERVICE_TOKEN_TTL_SECONDS},
        JWT_SECRET,
        algorithm="HS512",
    )
    return {"Authorization": f"Bearer {token}"}
