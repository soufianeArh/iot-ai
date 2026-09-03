FROM python:3.12-slim

# ffmpeg brings ffprobe, which is what validates RTSP streams.
# EasyAIoT's VIDEO/Dockerfile starts FROM pytorch/pytorch:...cuda12.8-devel (multi-GB)
# because it also runs inference. Phase 5 only probes, so slim + ffmpeg is enough.
# Regional mirror: deb.debian.org measured ~15-20KB/s from one deploy
# target, turning a routine apt-get into an hour-plus stall. This only
# rewrites sources inside THIS image's own build - nothing on any host.
RUN for f in /etc/apt/sources.list /etc/apt/sources.list.d/debian.sources; do \
      [ -f "$f" ] && sed -i 's|deb.debian.org|mirrors.aliyun.com|g; s|security.debian.org|mirrors.aliyun.com|g' "$f"; \
    done; \
    apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 6000

# 2 workers: one can block on a slow ffprobe while the other still serves.
CMD ["gunicorn", "--bind", "0.0.0.0:6000", "--workers", "2", "--timeout", "60", "run:app"]
