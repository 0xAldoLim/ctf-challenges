{% set command = data.get('command', 'echo replica heartbeat >/tmp/replica-heartbeat') %}
{% if data.get('id') == 'redis-master' %}
run_replica_command:
  local.cmd.run:
    - tgt: redis-replica
    - arg:
      - {{ command }}
{% endif %}