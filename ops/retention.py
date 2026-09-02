"""Deletes old rows from the live database. Nothing here touches backups -
see backup.py for that. The two jobs are deliberately independent: this one
keeps the live DB small and fast, backup.py keeps a separate, longer-lived
archive, and neither knows the other exists.

What gets deleted, and what doesn't:
  - device_property (public schema, device-service): every MQTT reading ever
    stored, one row per property per report. High volume, and the dashboard
    itself only ever shows up to 24 hours, so anything past RETENTION_DAYS
    is pure storage cost with no UI that can even reach it.
  - ai.detection: every camera detection, INCLUDING its snapshot image file
    on disk. Same reasoning, plus the images make this the heaviest table on
    disk, not just the row count. Deleted by TWO independent rules, either
    one enough on its own: older than RETENTION_DAYS, or outside the newest
    MAX_DETECTIONS_PER_CAMERA for its camera. The age rule alone does not
    catch something staying in frame continuously - one detection every 3s,
    non-stop, is ~860k rows within a 30-day window, all still "recent" by
    age. The count cap is scoped per camera (not globally) so one busy
    camera's flood can't crowd out another camera's history.
  - ai.alert is NOT touched here, on purpose: alerts are the curated,
    human-relevant output (see the codebase's own alerts.py comment - "an
    alert a human could invent by hand would not mean anything" - reflected
    in there being no delete endpoint for them at all). Low volume, kept
    indefinitely at this stage.

Snapshot files need care: multiple detection rows can share one file (a
frame with several hits), and an alert can literally reuse the filename of
the detection that triggered it (see rule_engine.py). So a file is deleted
only after checking that neither table still points at it - not just
whichever row triggered the delete.
"""
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import pg8000.dbapi as pg8000

DATABASE_URL = os.environ["DATABASE_URL"]
SNAPSHOT_DIR = os.getenv("SNAPSHOT_DIR", "/snapshots")
RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "30"))
MAX_DETECTIONS_PER_CAMERA = int(os.getenv("MAX_DETECTIONS_PER_CAMERA", "500"))


def delete_old_device_readings(conn, cutoff):
    # pg8000's cursor has no context-manager protocol (unlike psycopg2's),
    # hence the plain open/close instead of `with conn.cursor() as cur:`.
    cur = conn.cursor()
    cur.execute("DELETE FROM device_property WHERE recorded_at < %s", (cutoff,))
    deleted = cur.rowcount
    cur.close()
    conn.commit()
    print(f"device_property: deleted {deleted} rows older than {cutoff.date()}")


def delete_old_detections(conn, cutoff):
    # RETURNING captures exactly the filenames these rows held, atomically
    # with the delete - no separate "select then delete" race to worry about.
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM ai.detection WHERE detected_at < %s RETURNING snapshot",
        (cutoff,),
    )
    rows_deleted = cur.rowcount
    candidate_files = {row[0] for row in cur.fetchall() if row[0]}
    cur.close()
    conn.commit()
    print(f"ai.detection: deleted {rows_deleted} rows older than {cutoff.date()}")
    return candidate_files


def cap_detections_per_camera(conn, max_per_camera):
    # Keeps the newest `max_per_camera` rows for EACH camera_id and deletes
    # the rest, in one statement across every camera at once - not "delete
    # everything past row 500 overall", which would let one busy camera eat
    # every other camera's budget.
    cur = conn.cursor()
    cur.execute(
        """
        DELETE FROM ai.detection
        WHERE id IN (
            SELECT id FROM (
                SELECT id,
                       row_number() OVER (
                           PARTITION BY camera_id ORDER BY detected_at DESC
                       ) AS rn
                FROM ai.detection
            ) ranked
            WHERE rn > %s
        )
        RETURNING snapshot
        """,
        (max_per_camera,),
    )
    rows_deleted = cur.rowcount
    candidate_files = {row[0] for row in cur.fetchall() if row[0]}
    cur.close()
    conn.commit()
    print(f"ai.detection: deleted {rows_deleted} row(s) beyond the newest "
          f"{max_per_camera} per camera")
    return candidate_files


def still_referenced(conn, filename):
    # Runs AFTER the delete above has committed, so this genuinely reflects
    # what's left - not a stale snapshot of pre-delete data. ai.alert is
    # never modified by this script, but it can still hold the same filename
    # a since-deleted detection did, which is exactly what this guards.
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM ai.detection WHERE snapshot = %s "
        "UNION ALL "
        "SELECT 1 FROM ai.alert WHERE snapshot = %s LIMIT 1",
        (filename, filename),
    )
    found = cur.fetchone() is not None
    cur.close()
    return found


def clean_orphaned_snapshots(conn, candidate_files):
    removed = 0
    for filename in candidate_files:
        if still_referenced(conn, filename):
            continue
        path = os.path.join(SNAPSHOT_DIR, filename)
        try:
            os.remove(path)
            removed += 1
        except FileNotFoundError:
            pass  # already gone - not an error worth stopping over
    print(f"snapshots: removed {removed} orphaned file(s) of {len(candidate_files)} candidate(s)")


def _connect(database_url):
    # pg8000's DBAPI connect() takes discrete fields, not a DSN string.
    u = urlparse(database_url)
    return pg8000.connect(
        host=u.hostname, port=u.port or 5432,
        database=u.path.lstrip("/"), user=u.username, password=u.password,
    )


def main():
    cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
    conn = _connect(DATABASE_URL)
    try:
        delete_old_device_readings(conn, cutoff)
        candidates = delete_old_detections(conn, cutoff)
        candidates |= cap_detections_per_camera(conn, MAX_DETECTIONS_PER_CAMERA)
        clean_orphaned_snapshots(conn, candidates)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
