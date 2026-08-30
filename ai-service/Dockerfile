FROM python:3.12-slim

# ffmpeg: OpenCV needs it to open RTSP.
# libgl/libglib: OpenCV links against them even in the headless build.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    YOLO_CONFIG_DIR=/tmp/ultralytics

WORKDIR /app

# Install the CPU-only build of torch first. Plain `pip install ultralytics`
# pulls the CUDA build (~2.5 GB) even on machines with no GPU; the CPU wheels
# are a fraction of that and this stack has no GPU.
RUN pip install --no-cache-dir \
      --index-url https://download.pytorch.org/whl/cpu \
      torch==2.5.1 torchvision==0.20.1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Bake the model weights into the image so the container never downloads at
# runtime. yolov8n is the smallest model - fast enough on CPU.
RUN python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')" \
    && ls -l /app/yolov8n.pt

COPY . .

EXPOSE 7000

# ONE worker on purpose: the running inference threads live in this process's
# memory. A second worker would keep its own separate registry and the two would
# disagree about which cameras are being analysed.
CMD ["gunicorn", "--bind", "0.0.0.0:7000", "--workers", "1", "--threads", "4", "--timeout", "120", "run:app"]
