"""远程屏幕最小客户端。

每次快照新建连接：TightVNC 在同一条连接内重复请求全帧只返回缓存，
新建连接才会触发重新抓屏。输入可以直接走新连接，坐标用的是
framebuffer 绝对像素。
"""
import socket
import struct
import time

from PIL import Image

# ASCII 可打印区：X11 keysym 等于码位，可直接发送；下列符号在 US 布局上需要 Shift
SHIFTED = {
    "!": 0x31, "@": 0x32, "#": 0x33, "$": 0x34, "%": 0x35, "^": 0x36,
    "&": 0x37, "*": 0x38, "(": 0x39, ")": 0x30, "_": 0x2D, "+": 0x3D,
    "{": 0x5B, "}": 0x5D, "|": 0x5C, ":": 0x3B, '"': 0x27,
    "<": 0x2C, ">": 0x2E, "?": 0x2F, "~": 0x60,
}
CONTROL = {"\n": 0xFF0D, "\t": 0xFF09}
SHIFT = 0xFFE1


class UnsupportedFeature(RuntimeError):
    """服务端要求的能力当前未实现（编码/认证）。"""


class UnsupportedEncoding(UnsupportedFeature):
    """服务端使用了未实现的 RFB 编码。"""

    def __init__(self, encoding):
        self.encoding = encoding
        super().__init__(f"服务端使用未实现的 RFB 编码：{encoding}")


class UnsupportedAuth(UnsupportedFeature):
    """服务端要求认证，当前版本未实现（005-AR）。"""

    def __init__(self, types):
        self.types = list(types)
        super().__init__(
            f"服务端要求 VNC 认证（安全类型 {self.types}），当前版本未实现（005-AR）"
        )


class UnsupportedChar(ValueError):
    """非 ASCII（或控制符）字符，当前输入通道无法表达。"""


class RemoteScreen:
    """一台测试台的单个 framebuffer 会话。"""

    def __init__(self, host="192.168.1.68", port=5900):
        self.host = host
        self.port = port
        self.w = None
        self.h = None
        self.name = ""

    def _connect(self):
        s = socket.create_connection((self.host, self.port), 8)
        s.settimeout(25)

        def rx(n):
            buf = b""
            while len(buf) < n:
                chunk = s.recv(n - len(buf))
                if not chunk:
                    raise EOFError("connection closed")
                buf += chunk
            return buf

        rx(12)
        s.sendall(b"RFB 003.008\n")
        count = rx(1)[0]
        types = list(rx(count))
        if 1 not in types:
            raise UnsupportedAuth(types)
        s.sendall(bytes([1]))
        rx(4)
        s.sendall(bytes([1]))
        self.w, self.h = struct.unpack("!HH", rx(4))
        rx(16)
        name_len = struct.unpack("!I", rx(4))[0]
        self.name = rx(name_len).decode("latin-1")
        s.sendall(struct.pack("!BBH", 2, 0, 1) + struct.pack("!i", 0))
        return s, rx

    def _read_frame(self, s, rx):
        s.sendall(struct.pack("!BBHHHH", 3, 0, 0, 0, self.w, self.h))
        img = Image.new("RGB", (self.w, self.h))
        rows = 0
        non_zero = 0
        while rows < self.h:
            msg = rx(1)[0]
            if msg == 3:
                rx(3)
                n = int.from_bytes(rx(4), "big")
                rx(n)
                continue
            if msg == 2:
                continue
            if msg != 0:
                raise RuntimeError(f"unexpected message {msg}")
            rx(1)
            count = struct.unpack("!H", rx(2))[0]
            for _ in range(count):
                x, y, w, h = struct.unpack("!HHHH", rx(8))
                enc = struct.unpack("!i", rx(4))[0]
                if enc == 0:  # Raw
                    data = rx(w * h * 4)
                    non_zero += sum(1 for b in data if b)
                    tile = Image.frombuffer("RGB", (w, h), data, "raw", "BGRX", 0, 1)
                    img.paste(tile, (x, y))
                elif enc == 1:  # CopyRect：源矩形取自本帧已绘制区域
                    sx, sy = struct.unpack("!HH", rx(4))
                    tile = img.crop((sx, sy, sx + w, sy + h))
                    img.paste(tile, (x, y))
                else:
                    raise UnsupportedEncoding(enc)
                rows += h
        return img, non_zero

    def snapshot(self, attempts=3):
        """取当前画面。连接建立后的首帧常为空，需要再请求一次。"""
        last = None
        for _ in range(attempts):
            s, rx = self._connect()
            try:
                for _ in range(3):
                    img, non_zero = self._read_frame(s, rx)
                    last = img
                    if non_zero > 0:
                        return img
                    time.sleep(0.5)
            finally:
                s.close()
        if last is None:
            raise RuntimeError("no frame received")
        return last

    def _run(self, fn):
        s, _ = self._connect()
        try:
            fn(s)
        finally:
            time.sleep(0.1)
            s.close()

    def move(self, x, y):
        self._run(lambda s: s.sendall(struct.pack("!BBHH", 5, 0, x, y)))

    def click(self, x, y, hold=0.15):
        def action(s):
            s.sendall(struct.pack("!BBHH", 5, 0, x, y))
            time.sleep(0.2)
            s.sendall(struct.pack("!BBHH", 5, 1, x, y))
            time.sleep(hold)
            s.sendall(struct.pack("!BBHH", 5, 0, x, y))

        self._run(action)

    def tap(self, keysym):
        def action(s):
            s.sendall(struct.pack("!BBHI", 4, 1, 0, keysym))
            time.sleep(0.05)
            s.sendall(struct.pack("!BBHI", 4, 0, 0, keysym))

        self._run(action)

    def scroll(self, x, y, clicks=3, up=False):
        """滚轮：mask 的 bit3 向上、bit4 向下。"""
        mask = 0x08 if up else 0x10

        def action(s):
            for _ in range(clicks):
                s.sendall(struct.pack("!BBHH", 5, mask, x, y))
                time.sleep(0.05)
                s.sendall(struct.pack("!BBHH", 5, 0, x, y))
                time.sleep(0.08)

        self._run(action)

    def type_text(self, text):
        """按 US 布局逐字符输入。整串先校验：非 ASCII 直接抛 UnsupportedChar，绝不发半个词。"""
        bad = next((c for c in text
                    if (ord(c) > 0x7E or ord(c) < 0x20) and c not in CONTROL), None)
        if bad is not None:
            raise UnsupportedChar(f"{bad!r} (U+{ord(bad):04X})")
        for ch in text:
            if ch in CONTROL:
                self.tap(CONTROL[ch])
            elif ord(ch) > 0x7E or ord(ch) < 0x20:
                raise UnsupportedChar(f"{ch!r} (U+{ord(ch):04X})")
            elif ch in SHIFTED:
                self._shifted(SHIFTED[ch])
            elif ch.isupper():
                self._shifted(ord(ch.lower()))
            else:
                self.tap(ord(ch))

    def _shifted(self, keysym):
        def action(s):
            s.sendall(struct.pack("!BBHI", 4, 1, 0, SHIFT))
            time.sleep(0.04)
            s.sendall(struct.pack("!BBHI", 4, 1, 0, keysym))
            time.sleep(0.04)
            s.sendall(struct.pack("!BBHI", 4, 0, 0, keysym))
            time.sleep(0.04)
            s.sendall(struct.pack("!BBHI", 4, 0, 0, SHIFT))

        self._run(action)
