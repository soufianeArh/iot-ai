# Same major version as the PostgresSQL service, so pg_dump always matches
# the server instead of risking a version mismatch on restore.
FROM postgres:18

# Regional mirror: deb.debian.org was very slow from this deploy target.
# Only rewrites sources inside this image's own build, nothing on the host.
RUN for f in /etc/apt/sources.list /etc/apt/sources.list.d/debian.sources; do \
      [ -f "$f" ] && sed -i 's|deb.debian.org|mirrors.aliyun.com|g; s|security.debian.org|mirrors.aliyun.com|g' "$f"; \
    done; \
    apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip cron \
    && rm -rf /var/lib/apt/lists/*

# pg8000, not psycopg2: pure Python, so no C extension to build against this
# image's Python version. --break-system-packages works around Debian's
# PEP 668 restriction on a plain pip install, fine since nothing else
# runs in this image.
RUN pip3 install --no-cache-dir --break-system-packages pg8000==1.31.2

WORKDIR /app
COPY retention.py backup.py ./
COPY crontab /etc/cron.d/maintenance
RUN chmod 0644 /etc/cron.d/maintenance && crontab /etc/cron.d/maintenance

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

CMD ["/entrypoint.sh"]
