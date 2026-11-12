redis-sentinel-config:
  file.managed:
    - name: /usr/local/etc/redis/sentinel.conf
    - makedirs: True
    - contents: |
        port 26379

        requirepass {{ pillar['redis_password'] }}

        sentinel monitor mymaster master 6379 2
        sentinel auth-pass mymaster {{ pillar['redis_password'] }}

        sentinel resolve-hostnames yes
        sentinel down-after-milliseconds mymaster 5000
        sentinel failover-timeout mymaster 10000
        sentinel parallel-syncs mymaster 1
