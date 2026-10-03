#!/bin/sh
cleaner () {
    CLEANUP_DIR=$1;
    while true; do
        echo "$CLEANUP_DIR" $(whoami)
        find "$CLEANUP_DIR" -regex "$CLEANUP_DIR/.+" -mmin +30 -user author -delete
        sleep 60
    done
}

DATA_DIR="/service/data"

sed "s/SERVICE_PORT_PLACEHOLDER/${SERVICE_PORT:-9000}/" /etc/xinetd.conf.template > /etc/xinetd.conf

xinetd
chown author:author "$DATA_DIR"
cleaner "$DATA_DIR" &
tail -f /var/log/xinetd.log