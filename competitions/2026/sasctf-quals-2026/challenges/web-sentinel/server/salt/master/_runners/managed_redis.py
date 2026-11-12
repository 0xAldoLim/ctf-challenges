import salt.utils.event

# !DEPRECATED!
# Some time ago we used it like this:
# salt-call publish.runner managed_redis.run_redis_replica ...
# Now this runner is disabled
def run_redis_replica(note="echo replica heartbeat >/tmp/replica-heartbeat", **kwargs):
    caller = __opts__.get("id")
    if caller != "redis-master":
        return "You have no access"

    payload = {
        "id": caller,
        "command": note,
    }

    with salt.utils.event.get_event(
        "master",
        sock_dir=__opts__["sock_dir"],
        opts=__opts__,
        listen=False,
    ) as event:
        event.fire_event(payload, "redis/replica/execute")

    return True
