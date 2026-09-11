FROM python:3.12-slim

# Regional mirror: Debian's own servers stall badly from some deploy
# targets, so this rewrites both possible source file locations to Aliyun
# before installing ffmpeg, curl and the two OpenCV needs (libgl1, libglib2.0-0).
RUN for f in /etc/apt/sources.list /etc/apt/sources.list.d/debian.sources; do \
      [ -f "$f" ] && sed -i 's|deb.debian.org|mirrors.aliyun.com|g; s|security.debian.org|mirrors.aliyun.com|g' "$f"; \
    done; \
    apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    YOLO_CONFIG_DIR=/tmp/ultralytics

WORKDIR /app

# CPU-only torch first, no CUDA bundled in, then ultralytics (YOLO) itself
# from requirements.txt.
RUN pip install --no-cache-dir \
      --index-url https://download.pytorch.org/whl/cpu \
      torch==2.5.1 torchvision==0.20.1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-downloads the default weights at build time so the running app never has to.
RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')" \
    && ls -l /app/yolov8n.pt

COPY . .

EXPOSE 7000

# One worker, four threads. Timeout (120) matches llm_client.py's own
# LLM_TIMEOUT_SECONDS, a worker stuck past it gets killed and replaced.
CMD ["gunicorn", "--bind", "0.0.0.0:7000", "--workers", "1", "--threads", "4", "--timeout", "120", "run:app"]
