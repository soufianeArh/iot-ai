#!/bin/sh
set -eu
# cron jobs start with a near empty environment, so DATABASE_URL etc would
# be invisible otherwise. Dump the real environment once at startup and
# have crontab source it before each run.
printenv | sed -E 's/^([^=]+)=(.*)$/export \1="\2"/' > /app/env.sh

cron -f
