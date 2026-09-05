"""
Backs up the database and the snapshot images on disk, since pg_dump only
covers the database and has no idea the snapshots folder exists.

Kept independent from retention.py, so a bad retention run can't take the
backups down with it.

Old files are thinned over time: every daily backup for BACKUP_DAILY_KEEP
days, then one per week, then one per month, so a small number of files
still cover a long history. The two archives are thinned separately.
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
            # Newest first order means the first file seen for a given week
            # is that week's most recent backup, the one worth keeping.
            week_key = d.isocalendar()[:2]
            if week_key not in kept_weeks:
                kept_weeks.add(week_key)
                keep.add(path)
        elif d > monthly_cutoff:
            month_key = (d.year, d.month)
            if month_key not in kept_months:
                kept_months.add(month_key)
                keep.add(path)
        # else: past the whole window, gets removed below.

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
