"""
Deletes old rows from the live database on a schedule. See backup.py for
the separate archive job, this one only keeps the live DB small.

device_property and ai.detection get pruned past RETENTION_DAYS.
ai.detection also has a per camera row cap, since a busy camera can pile up
detections fast even within the retention window. ai.alert is never
touched here, alerts are kept indefinitely.

A snapshot file is only removed once no detection or alert row still
references it.
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
    # RETURNING captures the filenames atomically with the delete, avoiding
    # a separate select then delete race.
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
    # Keeps the newest max_per_camera rows per camera_id in one statement, so
    # one busy camera can't eat every other camera's budget.
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
    # Runs after the delete above commits, so this reflects what's actually
    # left. ai.alert can still hold the same filename a deleted detection
    # used, which is exactly what this checks for.
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
