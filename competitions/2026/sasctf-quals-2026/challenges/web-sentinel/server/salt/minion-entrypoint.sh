#!/bin/sh
set -eu

: "${MINION_ID:?MINION_ID is required}"

SALT_MASTER_HOST="${SALT_MASTER_HOST:-saltmaster}"

cat > /etc/salt/minion <<EOF
master: ${SALT_MASTER_HOST}
id: ${MINION_ID}
log_level: warning
retry_dns: 0
master_alive_interval: 5
verify_master_pubkey_sign: False
auth_timeout: 5
auth_tries: 1
request_channel_timeout: 5
request_channel_tries: 1
gather_job_timeout: 5
EOF

until nc -z "${SALT_MASTER_HOST}" 4505; do
    sleep 1
done

salt-minion -d -l warning

until timeout 20 salt-call --retcode-passthrough -t 5 state.apply; do
    sleep 2
done

if [ "$#" -gt 0 ]; then
    exec "$@"
fi

if [ -n "${SERVICE_COMMAND:-}" ]; then
    exec sh -c "${SERVICE_COMMAND}"
fi
