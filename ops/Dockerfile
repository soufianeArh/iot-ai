# Built FROM the same major version as the PostgresSQL service (see
# .setup/docker-compose.yml) rather than a generic python image + apt's
# postgresql-client: that would pull whatever client version Debian's default
# repo happens to carry, which can lag or lead the server's major version.
# pg_dump from a mismatched major version can silently skip newer features or
# refuse to restore cleanly - starting from postgres:18 guarantees pg_dump
# and the server are always the same version.
FROM postgres:18

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip cron \
    && rm -rf /var/lib/apt/lists/*

# pg8000, not psycopg2: pg8000 is pure Python, no C extension to compile or
# match against this image's Python version. psycopg2's C extension does not
# build against Python 3.13 (this base image's version) as of 2.9.9 - a
# version-compatibility problem a pure-Python driver never has in the first
# place. --break-system-packages: Debian's system pip refuses a plain global
# install (PEP 668) - fine here, this image runs nothing else that could
# conflict.
RUN pip3 install --no-cache-dir --break-system-packages pg8000==1.31.2

WORKDIR /app
COPY retention.py backup.py ./
COPY crontab /etc/cron.d/maintenance
RUN chmod 0644 /etc/cron.d/maintenance && crontab /etc/cron.d/maintenance

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

CMD ["/entrypoint.sh"]
