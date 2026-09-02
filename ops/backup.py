"""Backs up the two things a disaster could take with it: the database, and
the snapshot images sitting on disk next to it (pg_dump only ever covers the
former - it has no idea the /snapshots folder exists, so without this half
an alert's photo would be gone forever even with a perfect DB restore).
Each archive is thinned on its own, independent of retention.py and of
whatever it deletes from the live tables/files. That independence is the
actual point: if the retention job ever deletes more than it should (a bug,
a bad WHERE clause, run twice), these archives are what survive it. Syncing
them - deleting a backup the same day retention deletes what it backed up -
would defeat that; a backup with the same lifecycle as the data it protects
protects against nothing.

Rotation, once a file ages out of the most recent DAILY_KEEP days: keep only
the newest one per ISO week for WEEKLY_KEEP weeks, then only the newest per
calendar month for MONTHLY_KEEP months, then drop it. So at any moment you
have roughly DAILY_KEEP + WEEKLY_KEEP + MONTHLY_KEEP files covering a much
longer span than that many daily backups would. Both archives use this same
schedule, but each is thinned independently - a day where one succeeds and
the other doesn't (disk full, one job crashes) never affects the other's
rotation.
"""
import gzip
import os
import re
import subprocess
import tarfile
from datetime import date, datetime, timedelta

DATABASE_URL = os.environ["DATABASE_URL"]
SNAPSHOT_DIR = os.getenv("SNAPSHOT_DIR", "/snapshots")
BACKUP_DIR = os.getenv("BACKUP_DIR", "/backups")
DAILY_KEEP = int(os.getenv("BACKUP_DAILY_KEEP", "7"))
WEEKLY_KEEP = int(os.getenv("BACKUP_WEEKLY_KEEP", "4"))
MONTHLY_KEEP = int(os.getenv("BACKUP_MONTHLY_KEEP", "12"))

DB_RE = re.compile(r"^backup-(\d{4}-\d{2}-\d{2})\.sql\.gz$")
SNAPSHOTS_RE = re.compile(r"^snapshots-(\d{4}-\d{2}-\d{2})\.tar\.gz$")


def take_dump(today):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    out_path = os.path.join(BACKUP_DIR, f"backup-{today.isoformat()}.sql.gz")
    # Buffered in memory rather than piped straight to gzip: simpler, and at
    # this project's data volume the whole dump is a few MB at most, not
    # something that needs streaming.
    dump = subprocess.run(
        ["pg_dump", DATABASE_URL], stdout=subprocess.PIPE, check=True
    ).stdout
    with gzip.open(out_path, "wb") as f:
        f.write(dump)
    print(f"backup: wrote {out_path} ({len(dump)} bytes uncompressed)")


def take_snapshot_archive(today):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    out_path = os.path.join(BACKUP_DIR, f"snapshots-{today.isoformat()}.tar.gz")
    if not os.path.isdir(SNAPSHOT_DIR) or not os.listdir(SNAPSHOT_DIR):
        print(f"backup: {SNAPSHOT_DIR} is empty or missing, skipping snapshot archive")
        return
    with tarfile.open(out_path, "w:gz") as tar:
        tar.add(SNAPSHOT_DIR, arcname="snapshots")
    size = os.path.getsize(out_path)
    print(f"backup: wrote {out_path} ({size} bytes)")


def list_matching(pattern):
    found = []
    for name in os.listdir(BACKUP_DIR):
        m = pattern.match(name)
        if m:
            d = datetime.strptime(m.group(1), "%Y-%m-%d").date()
            found.append((d, os.path.join(BACKUP_DIR, name)))
    return found


def thin(today, pattern, label):
    files = sorted(list_matching(pattern), key=lambda x: x[0], reverse=True)  # newest first

    daily_cutoff = today - timedelta(days=DAILY_KEEP)
    weekly_cutoff = daily_cutoff - timedelta(weeks=WEEKLY_KEEP)
    monthly_cutoff = weekly_cutoff - timedelta(days=31 * MONTHLY_KEEP)

    keep = set()
    kept_weeks = set()
    kept_months = set()

    for d, path in files:
        if d > daily_cutoff:
            keep.add(path)  # inside the daily window: every one survives
        elif d > weekly_cutoff:
            # Newest-first order means the first file seen for a given week
            # is that week's most recent backup - the one worth keeping.
            week_key = d.isocalendar()[:2]
            if week_key not in kept_weeks:
                kept_weeks.add(week_key)
                keep.add(path)
        elif d > monthly_cutoff:
            month_key = (d.year, d.month)
            if month_key not in kept_months:
                kept_months.add(month_key)
                keep.add(path)
        # else: past the whole window - not kept, gets removed below.

    removed = 0
    for d, path in files:
        if path not in keep:
            os.remove(path)
            removed += 1
    print(f"{label}: kept {len(keep)} file(s), removed {removed} aged-out file(s)")


def main():
    today = date.today()
    take_dump(today)
    take_snapshot_archive(today)
    thin(today, DB_RE, "backup (db)")
    thin(today, SNAPSHOTS_RE, "backup (snapshots)")


if __name__ == "__main__":
    main()
