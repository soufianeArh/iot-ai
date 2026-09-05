# A fake camera: loops YOLO's own sample images into an RTSP stream, so the
# inference pipeline has something it is guaranteed to detect (people, a bus).
# Swap the images for a real .mp4 later, nothing downstream changes.
FROM python:3.12-slim

# Regional mirror: deb.debian.org was very slow from this deploy target.
# Only rewrites sources inside this image's own build, nothing on the host.
RUN for f in /etc/apt/sources.list /etc/apt/sources.list.d/debian.sources; do \
      [ -f "$f" ] && sed -i 's|deb.debian.org|mirrors.aliyun.com|g; s|security.debian.org|mirrors.aliyun.com|g' "$f"; \
    done; \
    apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /samples

# Ultralytics' canonical test images: bus.jpg (a bus and several people),
# zidane.jpg (two people). Baked in at build time so runtime needs no network.
RUN curl -fsSL -o bus.jpg    https://ultralytics.com/images/bus.jpg \
 && curl -fsSL -o zidane.jpg https://ultralytics.com/images/zidane.jpg

COPY playlist.txt /samples/playlist.txt
COPY publish.sh /publish.sh
RUN chmod +x /publish.sh

ENTRYPOINT ["/publish.sh"]
