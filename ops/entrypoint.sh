#!/bin/sh
set -eu
# cron starts each job with a near-empty environment, not this container's
# own - DATABASE_URL etc. would be invisible to the scripts otherwise. Dump
# the real environment to a file once at startup; crontab sources it before
# every run (see `. /app/env.sh &&` in ./crontab).
printenv | sed -E 's/^([^=]+)=(.*)$/export \1="\2"/' > /app/env.sh

cron -f
