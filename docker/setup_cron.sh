#!/bin/bash
: "${REFRESH_INTERVAL="0 0 * * *"}" # default to once a day at midnight
: "${EBIRD_LOCATION="MAJOR_REGION:world"}" # default to all sightings
set -ef
echo "using location: $EBIRD_LOCATION"
echo "using refresh interval: $REFRESH_INTERVAL"
echo "$REFRESH_INTERVAL /usr/local/bin/python3 -m bird_brained --location $EBIRD_LOCATION --headless > /proc/1/fd/1 2>&1" >> /etc/cron.d/brid_brained

printenv >> /etc/environment

/usr/local/bin/python3 -m bird_brained --location $EBIRD_LOCATION --headless

crontab /etc/cron.d/brid_brained
echo "Finished setup, starting cron daemon in foreground"
cron -f
