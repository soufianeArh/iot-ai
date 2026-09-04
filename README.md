## Technical

### device-service

**What it does**

The device registry and MQTT ingestion pipeline — the only service that speaks MQTT.

- Owns device identity: registration, status (ONLINE/OFFLINE), and every sensor reading reported over MQTT
- Surfaces MQTT traffic from unrecognized devices instead of silently dropping it

REST API (`/api/devices`):
- `GET /` list · `POST /` register · `GET /{id}` · `PUT /{id}` · `DELETE /{id}`
- `GET /{deviceId}/properties` — latest value of every key, or one key's history (`?key=...&limit=...`)
- `GET /unregistered` — MQTT traffic from device codes / product keys nobody registered, for spotting firmware misconfiguration

MQTT ingestion (EMQX, topics `iot/{productKey}/{deviceCode}/properties` and `.../status`):
- a property message → one row per key; a status message → flips ONLINE/OFFLINE
- an unrecognized device/productKey pair → tracked in memory, not the database (`productKey`, `deviceCode`, reason, count, first/last seen)
- **no way to delete an unregistered entry** — even after you register the device, its old sighting stays listed, frozen, in the UI
- it only disappears when: the 200-entry cap evicts it (oldest pushed out first), or the service restarts (memory wiped)

**Compose config**

- `build: context: ../device-service` — built from the local Dockerfile, not a prebuilt image
- `restart: always` — restarts automatically if the container dies
- `runtime: runc` — pinned explicitly, so it works regardless of what the host's Docker default-runtime is set to (a shared host might default to `nvidia` for other, GPU-dependent services)
- `depends_on`: `PostgresSQL` and `EMQX`, both gated on `condition: service_healthy` — won't start until both report healthy
- `expose: 8080` only — no host port; reachable externally solely through nginx's `/api/` and `/actuator/` proxy locations
- Env vars: `SPRING_DATASOURCE_URL/USERNAME/PASSWORD` (built from `POSTGRES_*`), `MQTT_BROKER_URL=tcp://EMQX:1883`
- Healthcheck: hits its own `/actuator/health` (15s interval, 5 retries, 60s start period before it's allowed to fail)
- `networks: easyaiot-network` — the shared compose network every service sits on

**Connections**

- **EMQX** (MQTT broker) — outbound connection *from* device-service *to* EMQX (client, not server); subscribes to `iot/+/+/properties` and `iot/+/+/status` on connect/reconnect
- **PostgreSQL** — JDBC, schema managed by Flyway (not by the entities — `ddl-auto: validate` only checks they match, never creates/alters)
- **nginx** — the only inbound path; proxies `/api/` and `/actuator/` to it. Nothing reaches device-service directly from outside the compose network — no host port is exposed

**Database**

No dedicated schema — lives in `public` (unlike video-service's `video` schema or ai-service's `ai` schema). Flyway-managed, two migrations:

- **`device`** — `id, name, device_code (unique), product_key, status (ONLINE/OFFLINE, default OFFLINE), created_at`. Indexed on `product_key`.
- **`device_property`** — `id, device_id (FK→device, ON DELETE CASCADE), property_key, property_value (TEXT), recorded_at`. One row per reading — full history, not a latest-only "shadow" table. Indexed on `(device_id, property_key, recorded_at DESC)`, which serves two query shapes: the newest reading per key (via Postgres `DISTINCT ON`) and one key's full history.

**Ops rules that touch it**

- **`retention.py`** (daily cron): deletes `device_property` rows older than `RETENTION_DAYS`. Age-only, no per-device row cap (unlike `ai.detection`'s age+cap combo) — the dashboard only ever queries up to 24h back, so anything older has no UI path that could reach it. `device` itself is never pruned — registrations aren't high-volume.
- **`backup.py`**: both tables are ordinary tables in the shared Postgres instance — included whole in the daily `pg_dump`, no special-casing needed.

### video-service

**What it does**

The camera registry and MediaMTX control plane — owns which RTSP cameras exist, never touches actual video.

- CRUD for cameras: register (name + RTSP URL, optional probe-only validate), list, get, delete
- Every registration is **verified before saving** — `ffprobe` connects briefly, reads codec/resolution/fps, and a camera that can't be reached is rejected outright, never stored broken
- Keeps MediaMTX's path mapping in sync: on register/delete it tells MediaMTX (over HTTP config API) which RTSP URL belongs to which camera; on its own startup it replays every camera in Postgres back into MediaMTX, since MediaMTX only holds that mapping in RAM and forgets it on restart
- Never proxies or touches video bytes — actual streaming is MediaMTX pulling RTSP on-demand (only while a viewer is watching) and serving HLS/WebRTC directly to the browser through nginx

REST API (`/video/camera`):
- `POST /` register (rejects if unreachable) · `GET /` list · `GET /{id}` · `DELETE /{id}`
- `POST /{id}/probe` — re-test an existing camera, unlike registration this **stores** the failure instead of rejecting
- `GET/POST/DELETE /{id}/stream` — query/register/unregister the camera's mapping in MediaMTX (config only, no RTSP made here)

**Compose config**

- `build: context: ../video-service` — built from the local Dockerfile, not a prebuilt image
- `restart: always`, `runtime: runc` — same reasoning as device-service (auto-restart, pinned runtime so a host's `nvidia` default doesn't hijack it)
- `depends_on`: **PostgreSQL only** (`condition: service_healthy`) — notably not MediaMTX, even though it calls it at startup. That's consistent with `resync_streams()`'s own retry logic (3 retries) picking up the slack instead of a hard compose-level dependency
- `expose: 6000` only — no host port, reachable solely through nginx
- Env vars: `DATABASE_URL`, `MEDIA_SERVER_API=http://mediamtx:9997`
- Healthcheck: hits its own `/video/health` (15s interval, 5 retries, 30s start period — half of device-service's 60s)
- `networks: easyaiot-network`

**Connections**

- **PostgreSQL** — SQLAlchemy, `video` schema (separate from device-service's `public`, deliberately — one service per schema, no cross-service table writes). No Flyway here: schema created via `db.create_all()` at startup, guarded by a Postgres advisory lock so multiple workers don't race each other creating it
- **MediaMTX** — outbound HTTP calls *from* video-service *to* MediaMTX's control API (`register_path`/`unregister_path`/`path_info`), config only. video-service never makes an RTSP connection or touches video bytes
- **nginx** — the only inbound path *into* video-service (proxies `/video/`); separately, nginx also proxies straight *to* MediaMTX for the actual HLS/WebRTC playback — that traffic never passes through video-service at all
- **Cameras (RTSP)** — no persistent connection from video-service; the one place it *does* connect is `ffprobe`, a short-lived, spawn-per-call subprocess used only to validate a camera at registration/reprobe time

**Database**

Own schema, `video` (not `public` — deliberately, so device-service's Flyway-managed tables and this stay isolated). No Flyway/Alembic yet: tables are created by `db.create_all()` at startup behind a Postgres advisory lock (`run.py`'s own docstring flags this explicitly as "NOT a substitute for migrations" — a future-cleanup admission, not an oversight).

One table:

- **`camera`** — `id, name, rtsp_url, status (UNKNOWN/REACHABLE/UNREACHABLE), codec, width, height, fps, last_error, last_probed_at, created_at`
- `rtsp_url` uniqueness is enforced only in application code (`register_camera`'s `filter_by(...).first()` check before insert), **not** a DB constraint — unlike device-service's `device_code`, which has a real unique index from its Flyway migration. Under concurrent requests this app-level check has a theoretical race; a DB-level constraint would close it
- No dedicated index beyond the implicit primary key — table stays small (one row per camera, not per reading), so no query pattern needs one yet

**Ops rules that touch it**

- **`retention.py`**: doesn't touch `video.camera` directly — it's a registry table (one row per camera, not a time-series), so there's nothing to age out. It does reference `camera_id` indirectly, in `ai.detection`'s per-camera retention cap (`MAX_DETECTIONS_PER_CAMERA`), but that logic and that table both belong to ai-service, not here
- **`backup.py`**: whole-instance `pg_dump`, no schema-specific handling — `video.camera` gets backed up automatically along with every other schema, same as device-service's tables
