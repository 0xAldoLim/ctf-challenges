import logging
import queue
import socket
import threading

import paramiko

from app.handlers import handle_shell
from app.hostkeys import load_host_keys
from app.logging_config import configure_logging
from app.server import SchizoServer
from app.settings import get_settings

log = logging.getLogger(__name__)


def handle_client(client, addr, host_keys, settings):
    peer = "%s:%s" % addr
    transport = None
    try:
        log.info("connection from %s", peer)
        client.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        transport = paramiko.Transport(client)
        transport.local_version = settings.banner
        for key in host_keys:
            transport.add_server_key(key)
        server = SchizoServer(peer)
        transport.start_server(server=server)

        while transport.is_active():
            try:
                item = server.work.get(timeout=settings.work_queue_timeout)
            except queue.Empty:
                continue
            if item[0] == "shell":
                handle_shell(item[1], peer)
    except Exception as exc:
        log.info("error with %s: %s", peer, exc)
    finally:
        if transport is not None:
            transport.close()
        log.info("disconnected %s", peer)


def main():
    configure_logging()
    settings = get_settings()
    host_keys = load_host_keys(settings)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((settings.bind, settings.port))
    sock.listen(settings.listen_backlog)
    log.info("listening on %s:%s", settings.bind, settings.port)

    while True:
        client, addr = sock.accept()
        thread = threading.Thread(
            target=handle_client,
            args=(client, addr, host_keys, settings),
            daemon=True,
        )
        thread.start()
