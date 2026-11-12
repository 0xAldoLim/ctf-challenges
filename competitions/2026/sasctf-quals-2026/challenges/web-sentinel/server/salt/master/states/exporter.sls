redis-exporter-config:
  file.managed:
    - name: /etc/exporter.env
    - makedirs: True
    - contents: |
        REDIS_ADDR=master:6379
        REDIS_PASSWORD={{ pillar['redis_password'] }}
