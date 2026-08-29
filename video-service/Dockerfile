FROM python:3.12-slim

# ffmpeg brings ffprobe, which is what validates RTSP streams.
# EasyAIoT's VIDEO/Dockerfile starts FROM pytorch/pytorch:...cuda12.8-devel (multi-GB)
# because it also runs inference. Phase 5 only probes, so slim + ffmpeg is enough.
RUN apt-get update \
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
