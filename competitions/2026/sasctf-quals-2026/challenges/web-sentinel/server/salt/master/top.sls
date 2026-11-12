base:
  'redis-master':
    - states.master
  'redis-replica':
    - states.replica
  'redis-sentinel':
    - states.sentinel
  'redis-exporter':
    - states.exporter
