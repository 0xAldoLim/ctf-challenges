redis-master-config:
  file.managed:
    - name: /usr/local/etc/redis/redis.conf
    - makedirs: True
    - contents: |
        bind 0.0.0.0
        protected-mode no
        port 6379

        requirepass {{ pillar['redis_password'] }}
        masterauth {{ pillar['redis_password'] }}

        appendonly yes
        appendfilename "appendonly.aof"

        save 900 1
        save 300 10
        save 60 10000
