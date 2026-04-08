#!/bin/sh
# Runs daily cleanup of ImgToPdfJob records older than 20 days.
# Runs on the Lightsail HOST at 02:00 UTC (= 23:00 ART, UTC-3).
#
# Crontab entry (on the host):
#   0 2 * * * /home/ubuntu/quatro_gnc/scripts/cleanup_cron.sh
#
# Log: /var/log/quatro_gnc_cleanup.log

docker compose -f /home/ubuntu/quatro_gnc/docker-compose.yml exec -T web \
    flask --app run.py cleanup-old-jobs >> /var/log/quatro_gnc_cleanup.log 2>&1
