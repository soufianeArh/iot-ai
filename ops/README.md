# ops

Two independent housekeeping jobs, run on a schedule by the `maintenance`
service in `.setup/docker-compose.yml`. Independent on purpose - see the
comments at the top of each script for why they must never be coupled.

- **`retention.py`** — deletes rows older than `RETENTION_DAYS` (default 30)
  from the live database: `device_property` (every MQTT reading) and
  `ai.detection` (every camera detection, plus its snapshot image file on
  disk). `ai.detection` is also capped at `MAX_DETECTIONS_PER_CAMERA` rows
  per camera (default 500) regardless of age - one camera detecting
  something continuously would otherwise stay "under 30 days" while still
  piling up hundreds of thousands of images. `ai.alert` is never touched -
  alerts are the curated output, kept indefinitely.
- **`backup.py`** — `pg_dump`s the whole database daily AND tars up
  `SNAPSHOT_DIR` (the alert/detection photos) daily - `pg_dump` only ever
  covers the database, it has no idea the photos on disk exist, so without
  this a DB restore would leave every alert pointing at a photo that no
  longer exists. Both archives are thinned the same way, independently:
  every one for the last `BACKUP_DAILY_KEEP` days (default 7), then one per
  week for `BACKUP_WEEKLY_KEEP` weeks (default 4), then one per month for
  `BACKUP_MONTHLY_KEEP` months (default 12).

## Running by hand (for testing, before waiting on cron)

```
docker compose exec maintenance python3 /app/backup.py
docker compose exec maintenance python3 /app/retention.py
```

## Getting backups off the box

`backup.py` only writes into `BACKUP_DIR` (bind-mounted to `../backups` on
the host - see docker-compose.yml). A backup that never leaves the same disk
as the database it protects isn't a real backup against losing that disk;
copy `../backups` off the server on whatever schedule you're comfortable
with (`scp`, rsync, object storage - anything that isn't "also on this box").

## Config (env vars, set in docker-compose.yml)

| Var | Default | Meaning |
|---|---|---|
| `RETENTION_DAYS` | 30 | how long a row stays live before `retention.py` deletes it |
| `MAX_DETECTIONS_PER_CAMERA` | 500 | hard cap on `ai.detection` rows per camera, regardless of age |
| `BACKUP_DAILY_KEEP` | 7 | how many most-recent daily dumps survive untouched |
| `BACKUP_WEEKLY_KEEP` | 4 | how many weekly buckets survive after that |
| `BACKUP_MONTHLY_KEEP` | 12 | how many monthly buckets survive after that |
