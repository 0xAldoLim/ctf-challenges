#!/bin/sh
set -eu

mode="${1:-}"
if [ -n "${FLAG:-}" ]; then
    if [ -e /flag.txt ]; then
        chmod 600 /flag.txt
    fi
    printf '%s\n' "$FLAG" >/flag.txt
    chmod 400 /flag.txt
    unset FLAG
fi

case "$mode" in
    api)
        exec su -m cloud -s /bin/sh -c "python3 main.py"
        ;;
    worker-public)
        exec su -m cloud -s /bin/sh -c "arq workers.public.WorkerSettings"
        ;;
    worker-private)
        exec su -m cloud -s /bin/sh -c "arq workers.private.WorkerSettings"
        ;;
    *)
        echo "usage: ./entry.sh api|worker-public|worker-private" >&2
        exit 2
        ;;
esac
