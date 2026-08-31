# NOTES

Why this project is built the way it is. The code says *what*; this says *why*.
Written up as each phase was finished, mostly from bugs that actually happened.

---

## 1. The stack

Everything is in `.setup/docker-compose.yml`. One network, one front door.

| container | what it is | port | reachable from host? |
|---|---|---|---|
| `nginx` | front door: static files + reverse proxy | 80 | yes — the only one |
| `device-service` | Spring Boot, devices + MQTT ingest | 8080 | no (`expose`) |
| `video-service` | Flask, camera registry | 6000 | no |
| `ai-service` | Flask + YOLOv8, inference workers | 7000 | no |
| `mediamtx` | media server: RTSP in → HLS/WebRTC out | 8554/8888/8889/9997 | 8189/udp only |
| `sample-camera-rtsp` | stock MediaMTX **pretending to be a camera** | 8554 | no |
| `sample-camera` | ffmpeg loop publishing into the above | — | no |
| `PostgresSQL` | one server, schema per service | 5434 | yes (dev only) |
| `Redis`, `EMQX` | cache, MQTT broker | 6379 / 1883, 18083 | yes |

**Why only nginx has a host port:** one origin means no CORS anywhere, one place
for TLS later, and no service is directly reachable from outside.

`sample-camera-rtsp` has **no folder** — it is a stock image with no `build:`, so
there is nothing to put on disk. Do not go looking for it.

---

## 2. Watching a camera, end to end

Two separate chains. They hit two different ports on MediaMTX and never mix.

### Chain A — register the path (control plane, no video)

```
browser   POST /video/camera/3/stream
   |
nginx     location ^~ /video/  ->  proxy_pass http://video-service:6000
   |                               (no rewrite: video-service owns /video itself)
video-service
          stream_register(3) -> read camera 3 from Postgres -> get rtsp_url
   |
video-service
          POST http://mediamtx:9997/v3/config/paths/add/cam3
          {"source": "rtsp://...", "sourceOnDemand": true, "rtspTransport": "tcp"}
   |
mediamtx  stores the mapping IN MEMORY. Dials nothing.
```

After this, MediaMTX holds a dictionary:

```
"cam1" -> rtsp://testrtsp:8554/live
"cam3" -> rtsp://sample-camera-rtsp:8554/live
```

Inspect it live: `docker exec nginx wget -qO- http://mediamtx:9997/v3/config/paths/list`

### Chain B — play it (data plane)

```
browser   GET /hls/cam3/index.m3u8
   |
nginx     rewrite ^/hls/(.*)$ /$1 break   ->  /cam3/index.m3u8
          proxy_pass http://mediamtx:8888
   |
mediamtx  first segment of the URI ("cam3") is the KEY into that dictionary.
          Looks up the source -> because sourceOnDemand, NOW dials the camera.
   |
mediamtx  RTSP client handshake against sample-camera-rtsp:8554
          OPTIONS -> DESCRIBE (SDP: H.264 960x1280 5fps) -> SETUP -> PLAY
          After PLAY the camera pushes frames down the open TCP socket forever.
   |
mediamtx  REPACKAGES (not re-encodes) H.264 -> init.mp4 + seg7.mp4, seg8.mp4 ...
          and writes index.m3u8 naming them.
   |
nginx     playlist back to the browser, Location + cookies rewritten (see section 4)
   |
hls.js    GET init.mp4, GET each segment, appendBuffer() into a MediaSource.
          Re-reads index.m3u8 every ~2s to find new segments.
   |
<video>   plays the buffer.
```

**~21 s on the first play.** That is the on-demand dial in step B. `cameras.html`
warms it with a plain `fetch()` first, because hls.js gives up after 10 s.

Meanwhile **ai-service opens its own RTSP connection** to
`rtsp://mediamtx:8554/cam3` and samples a frame every 3 s. Same source, second
consumer — the camera still sees only one connection. MediaMTX fans out.

---

## 3. What `.m3u8` actually is

A **text file listing video chunks**. Not video. It does not exist on disk before
the first request; MediaMTX builds it in memory when the stream starts.

```
#EXTM3U
#EXT-X-MEDIA-SEQUENCE:5                       <- segments 0-4 already deleted
#EXT-X-MAP:URI="..._init.mp4"                 <- decoder config, fetched ONCE
#EXTINF:2.00000,
..._seg7.mp4                                  <- 2 seconds of video
#EXTINF:2.00000,
..._seg8.mp4
#EXT-X-PART:DURATION=0.4,URI="..._part14.mp4" <- Low-Latency HLS
#EXT-X-PRELOAD-HINT:TYPE=PART,URI="..._part26.mp4"
```

Live video over nothing but ordinary GETs of ordinary files — which is why it
survives any proxy, CDN or firewall.

Things worth knowing:

- **One playlist per camera, not per request.** Ten viewers of cam3 share
  `/cam3/index.m3u8` and the same segments. Only `?session=` differs, and that
  exists only so MediaMTX can count who is watching.
- **Old segments are deleted and removed from the playlist together.** A dangling
  reference would 404 and stall the player. `#EXT-X-MEDIA-SEQUENCE` is how the
  player knows the window slid rather than that it missed something.
- **Real MediaMTX serves two levels**: `index.m3u8` is a *master* playlist listing
  variants (where YouTube would list 360p/720p/1080p); the variant playlist is
  the one listing segments.
- **`#EXT-X-PART` (0.4 s) exists because of `new Hls({ lowLatencyMode: true })`.**
  Without it you wait for whole 2 s segments; latency ~1 s instead of ~6 s.
- `#EXT-X-GAP` / `gap.mp4` = segments MediaMTX never produced. Leftovers from the
  UDP dropouts (section 6). They scroll out of the window on their own.
- Stop deleting segments and you have a VOD playlist (ends `#EXT-X-ENDLIST`).
  That is how you would add DVR/rewind later — same format, nothing thrown away.

**`appendBuffer` is not "display".** hls.js pushes bytes into a MediaSource
buffer; `<video>` plays that buffer at its own pace. There is no "show seg7,
then show seg8" — one continuous timeline, and segments are just how the bytes
arrive. Which is also why `autoplay` does nothing here: there is no `src` to
trigger it, so `MANIFEST_PARSED -> video.play()` is required.

Safari skips all of this: `video.canPlayType('application/vnd.apple.mpegurl')`
is true, so `video.src = url` and the OS plays HLS natively.

---

## 4. Why nginx looks like that

Every one of these lines is a bug that happened.

### `resolver 127.0.0.11` + variable upstreams

```nginx
resolver 127.0.0.11 valid=10s ipv6=off;
set $device_upstream device-service:8080;
location ^~ /api/ { proxy_pass http://$device_upstream; }
```

nginx resolves an upstream name **once at startup** and caches the IP forever.
Rebuild device-service, it gets a new IP, nginx 502s until you restart it.
A **variable** in `proxy_pass` defers resolution to request time.
(EasyAIoT does the same: `WEB/conf/nginx.edge.conf:71`, `:346`.)

### ...which forces the `rewrite`

```nginx
location ^~ /hls/ {
    rewrite ^/hls/(.*)$ /$1 break;
    proxy_pass http://$hls_upstream;
}
```

Normally `proxy_pass http://host/;` (trailing slash) strips the matched prefix.
**That does not work when proxy_pass contains a variable** — the URI is passed
through untouched, so `/hls/cam3/index.m3u8` would reach MediaMTX unchanged and
404. The prefix has to be removed by hand. `break` stops rewrite processing so
the rewritten URI is what gets proxied.

The `/hls/` prefix exists **only as a routing label for nginx** — one origin
serves five backends and it has to tell them apart. It is consumed at the door;
MediaMTX never sees it.

### the three cookie/redirect lines

MediaMTX answers the first HLS request with a 302 that sets a session cookie.
All three of these were needed before playback worked:

```nginx
proxy_redirect / /hls/;                     # Location is in MediaMTX's namespace
proxy_cookie_path / /hls/;                  # cookie Path=/cam3/, browser is on /hls/cam3/
proxy_cookie_flags ~ nosecure samesite=lax; # <- the one that actually broke it
```

**`Secure` was the real bug.** MediaMTX marks session cookies `Secure`, Chrome
silently drops those over plain HTTP, and every segment then failed the cookie
check. `curl` ignores the flag entirely, which is why curl tests passed while the
browser showed grey. **Lesson: test in a browser before declaring it fixed.**
When TLS lands in Phase 10 that line can go.

### nginx healthcheck uses `127.0.0.1`, not `localhost`

`localhost` resolves to `[::1]` in that image and `listen 80` binds IPv4 only —
the container reported `unhealthy` while serving traffic perfectly.

---

## 5. Control plane vs data plane

The idea the whole video half is built on:

- **Control plane** = who and where. Python, HTTP, small JSON, port 9997. Rare.
- **Data plane** = the bytes. Camera -> MediaMTX -> browser. Constant, large.

**Python never touches a video byte.** Same split for snapshots: ai-service
writes JPEGs to a shared volume and nginx serves them from `/snapshots/`
(mounted read-only there, so the web tier cannot modify what the AI tier made).

Consequence: **MediaMTX keeps paths in RAM only.** Restart it and every path is
gone while Postgres still has the cameras. Two defences:

1. `resync_streams()` at video-service startup replays every camera from Postgres.
2. `cameras.html` POSTs `/video/camera/{id}/stream` before playing. Idempotent
   and cheap, so every watch is self-healing.

Still missing: a **periodic** reconciler. Restart MediaMTX alone and paths stay
missing until somebody clicks watch. Fine here, not fine in production.

---

## 6. Phase log — bugs and their causes

### Phase 3 — nginx
- 502 after every rebuild -> upstream IP cached. -> `resolver` + variable (section 4).
- `unhealthy` while working fine -> `localhost` resolved to IPv6. -> `127.0.0.1`.

### Phase 4 — MQTT
- Subscriptions must be issued in **`connectComplete`**, not at startup. Subscribe
  once at boot and a broker restart silently loses them forever.
- Unknown `deviceCode` is **dropped, never auto-created**. A typo in a topic must
  not be able to create a device.

### Phase 5 — video-service
- `UniqueViolation: pg_namespace_nspname_index` -> two gunicorn workers raced on
  `CREATE SCHEMA IF NOT EXISTS`. -> `pg_advisory_lock(0x5645444F)` around init.
- Every public RTSP demo server on the internet is dead. -> run MediaMTX + ffmpeg
  locally instead.
- Renamed `start_stream`/`stop_stream` to `register_path`/`unregister_path`:
  the old names lied, they start nothing.

### Phase 6 — playback
- MediaMTX API "authentication error" -> the API is 127.0.0.1-only by default.
  -> `authInternalUsers` allowing `172.16.0.0/12`.
- 404 -> 302 loop -> grey screen: three separate causes, all in section 4.
- Grey screen part 2: 21 s cold start vs hls.js's 10 s manifest timeout
  -> pre-warm with `fetch()`. And `autoplay` never fires -> explicit `play()`.
- **Clicks silently swallowed**: `rows.innerHTML = html` on a 10 s poll destroyed
  the buttons mid-press. No `click` event fires if mousedown and mouseup land on
  different elements. -> `if (html !== rows.innerHTML)` before assigning.
  The same guard is in all three HTML pages.

### Phase 7 — YOLO
- **`self._stop` on a `threading.Thread` subclass shadows Thread's internal
  `_stop()` method**, which `join()` calls. Every stop died with
  `TypeError: 'Event' object is not callable`. -> rename to `_stop_event`.
  Never use `_stop`, `_target` or `_args` on a Thread subclass.
- **PyTorch grabs every CPU core** by default. With ffmpeg encoding, ffmpeg
  decoding, a media server and inference all competing, every healthcheck timed
  out and the whole stack went unhealthy. -> `torch.set_num_threads(2)` plus
  `OMP_NUM_THREADS=2` plus a hard `cpus: 2.0` ceiling in compose. All three.
- **RTSP defaults to UDP**, which drops packets across Docker's NAT: corrupted
  macroblocks, "reader is too slow, discarding 256 frames", and the source tears
  the connection down. Symptom was *3 frames analysed, 0 detections*.
  -> `"rtspTransport": "tcp"` in the path payload.
  Found by pulling one frame the way the worker does and looking at it: the frame
  was clean and YOLO found 2 people in it, so the bug had to be in the *reading*.
- Changing a compose **volume** needs `docker compose up -d <svc>` (recreate).
  `restart` keeps the old mounts — `/snapshots/` 404'd until the recreate.
- `mv yolov8n.pt /app/yolov8n.pt` failed as "same file": WORKDIR is already /app.

### Phase 8 — alerts
Built inside ai-service rather than as a fourth service: the data is already in
that process, so a separate service would have bought a Dockerfile you have
written three times in exchange for polling lag or an MQTT hop.

Two tables (`ai.alert_rule`, `ai.alert`), `app/services/rule_engine.py`,
`app/blueprints/alerts.py`, `web/html/alerts.html`, and **one hook** in
`worker.py` after the detections commit.

**A detection is a fact; an alert is a judgement.** The engine is three filters:

```
1. threshold   confidence >= rule.min_confidence      is the model sure?
2. quorum      >= rule.min_count in ONE frame         is it significant?
3. cooldown    nothing from this rule for N seconds   have we already said so?
```

**Dedup is the whole job.** The condition is trivial; not firing 300 times is
not. Measured over one run: **19 frames, ~60 detections, 3 alerts.**

Things that are the way they are on purpose:

- **Cooldown is keyed on (rule, camera)**, not on the rule. Two cameras seeing a
  person are two events and both must be reported.
- **The cooldown cache falls back to the table when cold.** Memory alone would
  re-announce everything the service is still looking at on every restart.
- **`_last_fired` is marked only after the commit succeeds.** Marking first would
  suppress the next window on the strength of an alert that was never stored.
- **`alert.rule_name` is a copy, and the FK is ON DELETE SET NULL.** Deleting a
  rule must not rewrite history — verified: the alert survived with
  `ruleId: null` and its name intact.
- **Rules are re-queried every frame, not cached.** ~0.3 queries/second/camera on
  an indexed table is cheaper than an invalidation bug.
- **Rule evaluation cannot kill inference.** It runs on the worker thread inside
  a try/except with a rollback; a bad rule costs alerts, not frames.
- **There is no `POST /ai/alerts`.** An alert a human could invent by hand would
  not mean anything.
- `PUT /ai/rules/{id}` is a **partial** update, which is why the page can toggle
  `enabled` by sending that field alone. It calls `rule_engine.forget()` so an
  edited cooldown takes effect immediately.

Not done: no notification anywhere (email, webhook, MQTT). An alert exists in a
table and on a page. Publishing to MQTT would reuse Phase 4 and close the loop —
MQTT in, MQTT out — and is the obvious next addition.

### Phase 8b — chat assistant

**This is tool calling, NOT RAG.** RAG (embed → vector search → stuff the prompt)
exists because prose has no schema. This data has one: "how many people did
camera 3 see today" is a `GROUP BY` with exactly one right answer, and retrieving
the *semantically nearest* rows would produce a confident wrong number. RAG would
be the right tool only if free-text were added — operator notes, manuals, incident
write-ups. There is none.

The loop, in `app/blueprints/chat.py`:

```
1. send conversation + tool schemas to the model
2. model replies with a TOOL CALL, not an answer
3. run the function locally, append the JSON result
4. go to 1  (cap: 4 rounds)
5. model replies in prose -> return it
```

The model never sees SQL and never touches Postgres. It supplies **arguments to
a form**: `{"name": "search_alerts", "arguments": {"camera_id": 3}}`. So it cannot
reach an unexposed table, cannot write, cannot DROP, and cannot run something
that takes 40 seconds. Every number in an answer came out of a real query.

Text-to-SQL — the model writing `SELECT ...` and you executing it — is the more
flexible design and needs a read-only role, a statement timeout, a forced LIMIT
and schema-only exposure before it is safe. Left as a later exercise.

Pieces: `services/chat_tools.py` (7 tools + JSON schemas), `services/llm_client.py`,
`blueprints/chat.py`, `web/html/chat.html`, and the `ollama` container.

Decisions worth keeping:

- **Written against the OpenAI `/v1/chat/completions` shape, not a vendor SDK.**
  Ollama, Groq, OpenAI and vLLM all speak it, so `LLM_BASE_URL` + `LLM_MODEL`
  switch providers with no code change. That matters because the local 1.5B model
  is the weakest link: pointing the same code at a bigger model instantly tells
  you whether a bad answer is your bug or the model's.
- **Ends up on Groq, not local.** The local path was built first and abandoned:
  this host has 7.9 GB of RAM, WSL2 gets ~half (3.78 GiB by default), and loading
  even `qwen2.5:1.5b` on top of the running stack exhausted the VM and **wedged
  the Docker engine itself** - every `docker` command returned 500 until it
  recovered on its own. Reproduced twice. On 8 GB, a local LLM is not viable
  alongside this stack; raising WSL2 memory would starve Windows instead.
  The ollama service is kept in compose, commented, as documentation of the
  offline path.
- **`openai/gpt-oss-20b` on Groq.** `llama-3.3-70b-versatile` has been retired and
  404s. Check what actually exists rather than trusting a model name:
  `curl -H "Authorization: Bearer $KEY" https://api.groq.com/openai/v1/models`
  and look for `"tools"` in `supported_features`.
- **`temperature: 0.1`.** The job is picking a tool and reporting numbers.
  Creativity here shows up as invented data.
- **Tool errors are returned as data, not raised.** A wrong argument comes back
  as `{"error": "bad arguments for count_detections: ..."}` so the model can
  retry. Small models invent arguments constantly; a 500 would end the turn.
- **`MAX_ROWS = 25`.** Not for Postgres's sake — for the prompt's. Small models
  drown in long JSON and start hallucinating.
- **`overview()` exists as one tool** because "anything I should look at?" is what
  people actually ask, and answering it from four separate tools is exactly where
  a 1.5B model loses the thread.
- **The server keeps no session.** The browser sends the history back each time,
  so restarting ai-service drops nobody's conversation.
- **`/ai/chat/health` is separate from `/ai/health`.** The chat being down must
  never mark the container unhealthy and take YOLO inference down with it.
- **Ownership is respected**: detections and alerts are queried directly (ours);
  cameras and devices go over HTTP to their owning services.
- The page shows **which tools each answer used**. That is the point of the
  exercise — you can watch the model choose, and verify the answer came from a
  real query.

Four bugs, all found by running it:

- **`health()` sent no `Authorization` header.** Ollama ignores it; every hosted
  provider returns 401. A perfectly good key looked invalid. Always test the
  dependency directly before blaming the credential.
- **`llama-3.3-70b-versatile` no longer exists on Groq.** Model names rot.
- **Groq free tier is 8k tokens/minute** - about 3-4 questions. Five in twenty
  seconds tripped it, and the raw provider error leaked to the user. Now caught
  as a 429 with a plain-English message.
- **gpt-oss-20b emits `{"": "{}"}` for a no-argument tool** - the whole argument
  object nested under an empty key. Dispatching that raised a TypeError, the
  model retried correctly (the errors-as-data design paying off), but it cost a
  wasted round trip on a token budget. Normalised in `chat.py`.

Also added a **per-request tool cache**: models re-request a tool they already
called this turn. Serving the cached rows with a "_note: answer now" halves the
token cost of a question.

Accuracy note: the model once answered *"Cameras 1 and 3 are reachable... Camera 1
is unreachable"* - contradicting itself in one sentence from correct data. Fixed
by a system-prompt line telling it to read each item's fields individually and
never merge items into one claim. **Tool results being right does not make the
answer right**; the prompt is doing real work.

Gotcha: the ollama **image** is ~3.2 GB and the **model** is a separate ~1 GB
download that is not in it. Without the named volume on `/root/.ollama` the model
re-downloads on every recreate.

---

## 7. Known weak spots

### The `cam{id}` naming coupling

Three files independently hardcode the same formula:

| file | role |
|---|---|
| `video-service/app/services/stream_service.py:37` | **decides** the name (`path_name`) |
| `web/html/cameras.html:125` | guesses it: `'/hls/cam' + id + '/index.m3u8'` |
| `ai-service/app/services/camera_client.py:45` | guesses it: `{media_rtsp}/cam{id}` |

Change the format in `stream_service.py` and the browser silently 404s. Nothing
links them but convention.

**The fix is already half-built**: `path_info()` returns `"hlsUrl"` and
`"webrtcUrl"` already, and `cameras.html` already calls that endpoint. It just
throws the answer away and rebuilds the URL itself. Use `s.hlsUrl` and only one
file knows the naming rule.

### Others

- **`create_all()` instead of Alembic** on the Python side. Fine for new tables,
  silently does nothing when a column changes. The Java side has Flyway.
- **No periodic reconciler** for MediaMTX paths (section 5).
- **No auth anywhere.** Everything is open on port 80.
- **No Python tests.** Java has 7 (`DeviceTopicTest`).
- **No `PUT`** on cameras — register and delete only.

---

## 8. Commands worth remembering

```bash
cd .setup

docker compose up -d --build <svc>   # ALWAYS --build if source or config changed;
                                     # a stale image cost an hour in Phase 2
docker compose up -d <svc>           # required after a VOLUME change (restart will not do)
docker compose restart <svc>         # enough for a bind-mounted file
docker exec nginx nginx -s reload    # nginx conf is bind-mounted: no rebuild needed

# poke an internal service from inside the network
docker exec nginx wget -qO- http://mediamtx:9997/v3/config/paths/list
docker exec nginx wget -qO- http://mediamtx:8888/cam3/index.m3u8
docker exec nginx wget -qO- http://ai-service:7000/ai/tasks
docker exec ai-service curl -s http://127.0.0.1:7000/ai/alerts/summary

# Phase 8b: the model is NOT in the ollama image - pull it once, it lives in
# the named volume. Check it is there with /ai/chat/health.
docker exec ollama ollama pull qwen2.5:1.5b
docker exec ollama ollama list
docker exec ai-service curl -s http://127.0.0.1:7000/ai/chat/health
```

Pages: `/` devices, `/cameras.html`, `/detections.html`, `/alerts.html`, `/chat.html`

---

## 9. Deliberate differences from EasyAIoT

| EasyAIoT | here | why |
|---|---|---|
| `-api` / `-biz` module split per service | one module | the split pays off across teams, not solo |
| MyBatis Plus | JPA + Flyway | versioned migrations; `ddl-auto: validate` |
| Lombok | plain Java | nothing hidden while learning |
| ffmpeg process per camera -> RTMP -> SRS | MediaMTX pulls natively | no child processes to supervise |
| Nacos service discovery | Docker DNS | one machine |
