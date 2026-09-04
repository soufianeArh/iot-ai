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
