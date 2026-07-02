#!/bin/bash
: "${REFRESH_INTERVAL="0 0 * * *"}" # default to once a day at midnight
: "${EBIRD_REGION="world"}" # default to all sightings
set -ef
echo "using region: $EBIRD_REGION"
echo "using refresh interval: $REFRESH_INTERVAL"
echo "$REFRESH_INTERVAL /usr/local/bin/python3 -m bird_brained --region $EBIRD_REGION --headless > /proc/1/fd/1 2>&1" >> /etc/cron.d/brid_brained

printenv >> /etc/environment

crontab /etc/cron.d/brid_brained
echo "Finished setup, starting cron daemon in foreground"
cron -f
