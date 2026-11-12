import codecs
from enum import IntEnum


class ParserState(IntEnum):
    NORMAL = 0
    ESCAPE = 1
    CSI = 2
    SS3 = 3


class LineEditor:
    def __init__(self, channel, prompt, on_command):
        self.channel = channel
        self.prompt = prompt
        self.on_command = on_command
        self.buf = []
        self.cursor = 0
        self.history = []
        self.hist_pos = None
        self.saved = []
        self.decoder = codecs.getincrementaldecoder("utf-8")("replace")
        self.state = ParserState.NORMAL
        self.params = bytearray()
        self.swallow_lf = False
        self.closed = False

    def start(self):
        self._send(self.prompt)

    def feed(self, data):
        for byte in data:
            if self.closed:
                break
            self._step(byte)

    def _send(self, data):
        if isinstance(data, str):
            data = data.encode("utf-8")
        self.channel.sendall(data)

    def _step(self, byte):
        if self.state == ParserState.NORMAL:
            self._step_normal(byte)
        elif self.state == ParserState.ESCAPE:
            self._step_escape(byte)
        elif self.state == ParserState.CSI:
            self._step_csi(byte)
        else:
            self._step_ss3(byte)

    def _step_normal(self, byte):
        if byte == 10 and self.swallow_lf:
            self.swallow_lf = False
            return
        self.swallow_lf = False
        if byte == 27:
            self.state = ParserState.ESCAPE
            self.params = bytearray()
        elif byte == 13:
            self.swallow_lf = True
            self._submit()
        elif byte == 10:
            self._submit()
        elif byte in (8, 127):
            self._backspace()
        elif byte == 3:
            self._abort()
        elif byte == 4:
            if not self.buf:
                self._logout()
        elif byte == 1:
            self._move_home()
        elif byte == 5:
            self._move_end()
        elif byte == 21:
            self._kill_line()
        elif byte == 11:
            self._kill_to_end()
        elif byte == 12:
            self._clear_screen()
        elif byte < 32:
            return
        else:
            for ch in self.decoder.decode(bytes([byte])):
                if ch.isprintable():
                    self._insert(ch)

    def _step_escape(self, byte):
        if byte == 0x5B:
            self.state = ParserState.CSI
            self.params = bytearray()
        elif byte == 0x4F:
            self.state = ParserState.SS3
        else:
            self.state = ParserState.NORMAL
            self._step_normal(byte)

    def _step_csi(self, byte):
        if 0x30 <= byte <= 0x3F:
            self.params.append(byte)
        elif 0x40 <= byte <= 0x7E:
            self.state = ParserState.NORMAL
            self._dispatch_csi(chr(byte), self.params.decode("ascii", "ignore"))
        else:
            self.state = ParserState.NORMAL

    def _step_ss3(self, byte):
        self.state = ParserState.NORMAL
        self._dispatch_arrow(chr(byte))

    def _dispatch_csi(self, final, params):
        if final == "~":
            code = params.split(";")[0]
            action = {
                "1": self._move_home,
                "7": self._move_home,
                "4": self._move_end,
                "8": self._move_end,
                "3": self._delete,
            }.get(code)
            if action is not None:
                action()
        else:
            self._dispatch_arrow(final)

    def _dispatch_arrow(self, final):
        if final == "A":
            self._history_prev()
        elif final == "B":
            self._history_next()
        elif final == "C":
            self._move_right()
        elif final == "D":
            self._move_left()
        elif final == "H":
            self._move_home()
        elif final == "F":
            self._move_end()

    def _insert(self, ch):
        self.buf.insert(self.cursor, ch)
        self.cursor += 1
        tail = "".join(self.buf[self.cursor - 1:])
        self._send(tail)
        back = len(self.buf) - self.cursor
        if back:
            self._send(b"\b" * back)

    def _backspace(self):
        if self.cursor == 0:
            return
        self.cursor -= 1
        del self.buf[self.cursor]
        tail = "".join(self.buf[self.cursor:])
        self._send(b"\b" + tail.encode("utf-8") + b" ")
        self._send(b"\b" * (len(tail) + 1))

    def _delete(self):
        if self.cursor >= len(self.buf):
            return
        del self.buf[self.cursor]
        tail = "".join(self.buf[self.cursor:])
        self._send(tail.encode("utf-8") + b" ")
        self._send(b"\b" * (len(tail) + 1))

    def _move_left(self):
        if self.cursor > 0:
            self.cursor -= 1
            self._send(b"\b")

    def _move_right(self):
        if self.cursor < len(self.buf):
            self._send(self.buf[self.cursor])
            self.cursor += 1

    def _move_home(self):
        if self.cursor > 0:
            self._send(b"\b" * self.cursor)
            self.cursor = 0

    def _move_end(self):
        if self.cursor < len(self.buf):
            self._send("".join(self.buf[self.cursor:]))
            self.cursor = len(self.buf)

    def _kill_line(self):
        if self.cursor > 0:
            self._send(b"\b" * self.cursor)
        self._send(b"\x1b[K")
        self.buf = []
        self.cursor = 0

    def _kill_to_end(self):
        if self.cursor < len(self.buf):
            del self.buf[self.cursor:]
            self._send(b"\x1b[K")

    def _clear_screen(self):
        self._send(b"\x1b[H\x1b[2J")
        self._send(self.prompt)
        self._send("".join(self.buf))
        back = len(self.buf) - self.cursor
        if back:
            self._send(b"\b" * back)

    def _abort(self):
        self._send(b"^C\r\n")
        self.buf = []
        self.cursor = 0
        self.hist_pos = None
        self.saved = []
        self._send(self.prompt)

    def _logout(self):
        self._send(b"logout\r\n")
        self.closed = True

    def _replace_line(self, new_chars):
        if self.cursor > 0:
            self._send(b"\b" * self.cursor)
        self._send(b"\x1b[K")
        self.buf = list(new_chars)
        self.cursor = len(self.buf)
        if self.buf:
            self._send("".join(self.buf))

    def _history_prev(self):
        if not self.history:
            return
        if self.hist_pos is None:
            self.saved = list(self.buf)
            self.hist_pos = len(self.history) - 1
        elif self.hist_pos > 0:
            self.hist_pos -= 1
        else:
            return
        self._replace_line(self.history[self.hist_pos])

    def _history_next(self):
        if self.hist_pos is None:
            return
        if self.hist_pos < len(self.history) - 1:
            self.hist_pos += 1
            self._replace_line(self.history[self.hist_pos])
        else:
            self.hist_pos = None
            self._replace_line(self.saved)
            self.saved = []

    def _submit(self):
        self._send(b"\r\n")
        text = "".join(self.buf)
        self.buf = []
        self.cursor = 0
        self.hist_pos = None
        self.saved = []
        if text:
            if not self.history or self.history[-1] != text:
                self.history.append(text)
            new_prompt = self.on_command(text)
            if isinstance(new_prompt, str):
                self.prompt = new_prompt
        self._send(self.prompt)
