"""
  /ai/rules   full CRUD. A human writes these; they are configuration.
  /ai/alerts  read + acknowledge only. The engine writes these; they are history.

There is deliberately no POST /ai/alerts. An alert that a human could invent by
hand would not mean anything.
"""
import logging

from flask import Blueprint, jsonify, request

from app import db
from app.models import Alert, AlertRule, utcnow
from app.services import rule_engine
from app.services.rule_engine import RuleError

log = logging.getLogger(__name__)

alerts_bp = Blueprint("alerts", __name__)


@alerts_bp.errorhandler(RuleError)
#caches rule error
def _handle_rule_error(exc):
    return jsonify({"status": 400, "error": "Bad Request", "message": str(exc)}), 400


# --------------------------------------------------------- rules

@alerts_bp.route("/rules", methods=["GET"])
#returns every AlertRule row, ordered by id, as JSON
def list_rules():
    rows = AlertRule.query.order_by(AlertRule.id).all()
    return jsonify([r.to_dict() for r in rows])


@alerts_bp.route("/rules", methods=["POST"])
def create_rule():
    fields = rule_engine.validate(request.get_json(silent=True) or {})
    rule = AlertRule(**fields)
    db.session.add(rule)
    db.session.commit()
    log.info("rule %s created: %s", rule.id, rule.name)
    return jsonify(rule.to_dict()), 201


@alerts_bp.route("/rules/<int:rule_id>", methods=["GET"])
def get_rule(rule_id):
    #fetch one rule by id, 404 if it doesn't exist
    # DEAD code in back-front but kep to complete CRUD
    rule = db.session.get(AlertRule, rule_id)
    if rule is None:
        return jsonify({"status": 404, "error": "Not Found"}), 404
    return jsonify(rule.to_dict())


@alerts_bp.route("/rules/<int:rule_id>", methods=["PUT"])
def update_rule(rule_id):
    #check if the rule to update already exists
    rule = db.session.get(AlertRule, rule_id)
    if rule is None:
        return jsonify({"status": 404, "error": "Not Found"}), 404

    # Partial update: anything absent keeps its current value.
    #fills the empty fields with old values
    fields = rule_engine.validate(request.get_json(silent=True) or {}, existing=rule)
    for key, value in fields.items():
        setattr(rule, key, value)
    db.session.commit()

    # The cooldown cache is keyed on the rule. Editing one (especially its
    # cooldown) must not leave the old timing in force.
    rule_engine.forget(rule_id)
    return jsonify(rule.to_dict())


@alerts_bp.route("/rules/<int:rule_id>", methods=["DELETE"])
def delete_rule(rule_id):
    rule = db.session.get(AlertRule, rule_id)
    if rule is None:
        return jsonify({"status": 404, "error": "Not Found"}), 404
    db.session.delete(rule)
    db.session.commit()
    rule_engine.forget(rule_id)
    # Alerts raised by this rule survive: the FK is ON DELETE SET NULL and each
    # alert carries a copy of the rule name.
    return "", 204


# ---------------------------------------------------------- alerts

@alerts_bp.route("/alerts", methods=["GET"])
def list_alerts():
    query = Alert.query

    camera_id = request.args.get("cameraId", type=int)
    if camera_id is not None:
        query = query.filter_by(camera_id=camera_id)

    severity = request.args.get("severity")
    if severity:
        query = query.filter_by(severity=severity.upper())

    # ?acknowledged=false is the view an operator actually wants: the open ones.
    ack = request.args.get("acknowledged")
    if ack is not None:
        query = query.filter_by(acknowledged=ack.lower() in ("1", "true", "yes"))

    limit = min(request.args.get("limit", default=50, type=int), 500)
    rows = query.order_by(Alert.raised_at.desc()).limit(limit).all()
    return jsonify([r.to_dict() for r in rows])


@alerts_bp.route("/alerts/<int:alert_id>/ack", methods=["POST"])
def acknowledge(alert_id):
    """Mark one alert as seen by a human. Idempotent."""
    alert = db.session.get(Alert, alert_id)
    if alert is None:
        return jsonify({"status": 404, "error": "Not Found"}), 404
    if not alert.acknowledged:
        alert.acknowledged = True
        alert.acknowledged_at = utcnow()
        db.session.commit()
    return jsonify(alert.to_dict())


@alerts_bp.route("/alerts/summary", methods=["GET"])
def summary():
    # counts showing on top of alert page!!
    rows = (db.session.query(Alert.severity, db.func.count(Alert.id))
            .group_by(Alert.severity).all())
    open_count = Alert.query.filter_by(acknowledged=False).count()
    return jsonify({
        "bySeverity": {severity: count for severity, count in rows},
        "total": sum(count for _, count in rows),
        "unacknowledged": open_count,
    })
