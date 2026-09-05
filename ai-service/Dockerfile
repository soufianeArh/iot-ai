FROM python:3.12-slim

# for/sed loop check for possible debin source ( sources.list vs sources.list.d/debian.sources
# apt-get update + install pulls ffmpeg, curl, libgl1, libglib2.0-0
# from the Aliyun mirror instead of Debian's own servers.
#rm -rf /var/lib/apt/lists/* at the end clears the downloaded package index to keep the image layer small
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

# Install the CPU-only build of torch first. (no CUDA/GPU code bundled in)
#PyTorch is the neural-network engine underneath YOLO;
# ultralytics (the YOLO library) is written using PyTorch's tensors and layers
RUN pip install --no-cache-dir \
      --index-url https://download.pytorch.org/whl/cpu \
      torch==2.5.1 torchvision==0.20.1

#line 8: ultralytics==8.3.40. That's the YOLO library itself.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# import yolo class and .pt weights
# It's purely caching: pre-downloading the file once at build time  \
# so the app code never has
RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')" \
    && ls -l /app/yolov8n.pt

COPY . .

EXPOSE 7000

# ONE worker on purpose: 4threads
# 120 matches llm_client.py's own LLM_TIMEOUT_SECONDS
# Gunicorn's master process expects each worker to "check in" periodically to prove it's alive 120s here\
# If a worker goes silent for longer than
#  --timeout seconds (because it's still stuck processing one request), the master assumes that worker is dead/stuck, sends it SIGKILL, and
  spawns a fresh replacement worker process.
CMD ["gunicorn", "--bind", "0.0.0.0:7000", "--workers", "1", "--threads", "4", "--timeout", "120", "run:app"]
