#!/bin/sh
# File: /entry.sh

# Gets sentinel.sls from salt master
if [ ! -f /usr/local/etc/redis/sentinel.conf ]; then
    /usr/local/bin/minion-entrypoint.sh
fi

# Disables forks and execve for santinel, we don't need RCE in it 
/usr/local/bin/redis-sentinel-seccomp \
    redis-sentinel /usr/local/etc/redis/sentinel.conf
