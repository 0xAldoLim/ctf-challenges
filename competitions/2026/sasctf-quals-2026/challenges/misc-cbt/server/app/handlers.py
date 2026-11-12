import logging

from app.agent import ShellSession
from app.line_editor import LineEditor
from app.pow import run_pow_challenge
from app.settings import get_settings

log = logging.getLogger(__name__)


def _to_crlf(output):
    if not output:
        return b""
    text = output.replace("\r\n", "\n").replace("\n", "\r\n")
    if not text.endswith("\r\n"):
        text += "\r\n"
    return text.encode("utf-8", "replace")


def handle_shell(channel, peer):
    settings = get_settings()
    log.info("shell opened from %s", peer)
    passed_pow, initial_data = run_pow_challenge(channel, settings, bits=settings.pow_bits)
    if not passed_pow:
        try:
            channel.send_exit_status(1)
        except Exception:
            pass
        channel.close()
        return

    shell = ShellSession()

    def on_command(text):
        log.info("shell command from %s: %s", peer, text)
        result = shell.execute(text)
        payload = _to_crlf(result.output)
        if payload:
            channel.sendall(payload)
        if shell.should_close:
            editor.closed = True
            return None
        return shell.prompt()

    editor = LineEditor(channel, shell.prompt(), on_command)
    try:
        editor.start()
        if initial_data:
            editor.feed(initial_data)
        while not editor.closed:
            data = channel.recv(settings.recv_buffer_size)
            if not data:
                break
            editor.feed(data)
    finally:
        try:
            channel.send_exit_status(0)
        except Exception:
            pass
        channel.close()
