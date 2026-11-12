import queue

import paramiko

from app.settings import get_settings


class SchizoServer(paramiko.ServerInterface):
    def __init__(self, peer):
        self.peer = peer
        self.work = queue.Queue()
        self.settings = get_settings()

    def check_channel_request(self, kind, chanid):
        if kind == "session":
            return paramiko.OPEN_SUCCEEDED
        if kind in ("direct-streamlocal@openssh.com", "tun@openssh.com"):
            return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED
        return paramiko.OPEN_FAILED_UNKNOWN_CHANNEL_TYPE

    def check_channel_direct_tcpip_request(self, chanid, origin, destination):
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def check_global_request(self, kind, msg):
        if kind == "no-more-sessions@openssh.com":
            return True
        return False

    def check_auth_password(self, username, password):
        if username == self.settings.username and password == self.settings.password:
            return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED

    def get_allowed_auths(self, username):
        return "password"

    def check_channel_pty_request(self, *args):
        return True

    def check_channel_window_change_request(self, *args):
        return True

    def check_channel_shell_request(self, channel):
        self.work.put(("shell", channel))
        return True

    def check_channel_exec_request(self, channel, command):
        return False
