#!/bin/sh
set -eu

DEFAULT_FLAG='SAS{placeholder}'

REDIS_PASSWORD="$(python3 - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
)"

FLAG_VALUE="${FLAG:-$DEFAULT_FLAG}"

cat > /srv/pillar/common.sls <<EOF
redis_password: ${REDIS_PASSWORD}
EOF

printf '%s\n' "${FLAG_VALUE}" > /flag.txt

exec salt-master -l warning
