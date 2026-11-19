"""端到端验证 VNC 认证：本地起一个最小 RFB 服务端（要求安全类型 2）。

比假 socket 更进一步：真实的 TCP 连接、真实的握手顺序、真实的一帧画面。
覆盖 005-AR 的验收点：
- 提供正确密码 → 握手成功并取到画面；
- 密码错误 → 客户端得到 NO_CONNECTION（协议层映射），且原因可读；
- 服务端要求认证但客户端没配密码 → NO_CONNECTION 并提示配置项；
- 服务端提供 None（类型 1）时不受影响。
"""
import os
import socket
import struct
import sys
import threading
import unittest

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import vnc_auth
from remote_screen import RemoteScreen
from screen_protocol import ScreenProtocol
from vnc_auth import PASSWORD_ENV

W = H = 8
PIXEL = bytes([0x30, 0x60, 0x90, 0x00])  # B,G,R,X


class FakeLocator:
    def scan(self, image, region=None, col_w=480):
        return []

    def scan_columns(self, image, col_w=480):
        return []

    def find(self, image, needle, region=None, min_score=0.6):
        return None

    def find_all(self, image, needle, region=None, min_score=0.6):
        return []


class MiniRfbServer(threading.Thread):
    """只做一件事：按 RFB 3.8 握手，认证通过后发一帧 Raw。"""

    def __init__(self, password=None, security=2):
        super().__init__(daemon=True)
        self.password = password
        self.security = security
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(1)
        self.port = self.sock.getsockname()[1]
        self.error = None
        self.authed = False

    def run(self):
        try:
            conn, _ = self.sock.accept()
            with conn:
                conn.sendall(b"RFB 003.008\n")
                conn.recv(12)
                conn.sendall(bytes([1, self.security]))
                kind = conn.recv(1)[0]
                if kind != self.security:
                    self.error = f"客户端选了 {kind}"
                    return
                if self.security == 2:
                    challenge = bytes(range(16))
                    conn.sendall(challenge)
                    response = b""
                    while len(response) < 16:
                        response += conn.recv(16 - len(response))
                    expected = vnc_auth.auth_response(self.password, challenge)
                    if response != expected:
                        conn.sendall(struct.pack("!I", 1))
                        return
                    self.authed = True
                    conn.sendall(struct.pack("!I", 0))
                else:
                    conn.sendall(struct.pack("!I", 0))
                conn.recv(1)  # ClientInit
                name = b"mini-rfb"
                conn.sendall(struct.pack("!HH", W, H) + b"\x20" * 16
                             + struct.pack("!I", len(name)) + name)
                conn.recv(1024)  # SetEncodings
                conn.recv(10)    # FramebufferUpdateRequest
                conn.sendall(struct.pack("!BBH", 0, 0, 1)
                             + struct.pack("!HHHHi", 0, 0, W, H, 0)
                             + PIXEL * (W * H))
        except Exception as exc:  # noqa: BLE001 - 测试服务端记录任何异常
            self.error = f"{type(exc).__name__}: {exc}"
        finally:
            self.sock.close()


class VncAuthEndToEndTest(unittest.TestCase):
    def setUp(self):
        self._old = os.environ.get(PASSWORD_ENV)
        os.environ.pop(PASSWORD_ENV, None)

    def tearDown(self):
        if self._old is None:
            os.environ.pop(PASSWORD_ENV, None)
        else:
            os.environ[PASSWORD_ENV] = self._old

    def protocol(self, server):
        return ScreenProtocol(RemoteScreen("127.0.0.1", server.port), FakeLocator(),
                              os.path.join(os.path.dirname(__file__), ".evidence-test"), meta={})

    def test_correct_password_gets_screen(self):
        server = MiniRfbServer(password="s3cret!")
        server.start()
        os.environ[PASSWORD_ENV] = "s3cret!"
        result = self.protocol(server).describe()
        server.join(timeout=5)
        self.assertTrue(result["ok"], result)
        self.assertTrue(server.authed, server.error)
        self.assertEqual((result["screen"]["w"], result["screen"]["h"]), (W, H))

    def test_wrong_password_maps_to_no_connection(self):
        server = MiniRfbServer(password="s3cret!")
        server.start()
        os.environ[PASSWORD_ENV] = "wrong!"
        result = self.protocol(server).describe()
        server.join(timeout=5)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "NO_CONNECTION")
        self.assertIn("认证失败", result["error"]["message"])

    def test_missing_password_hint(self):
        server = MiniRfbServer(password="s3cret!")
        server.start()
        result = self.protocol(server).describe()
        server.join(timeout=5)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "NO_CONNECTION")
        self.assertIn(PASSWORD_ENV, result["error"]["hint"])

    def test_none_security_unaffected(self):
        server = MiniRfbServer(security=1)
        server.start()
        result = self.protocol(server).describe()
        server.join(timeout=5)
        self.assertTrue(result["ok"], result)
        self.assertEqual((result["screen"]["w"], result["screen"]["h"]), (W, H))


if __name__ == "__main__":
    unittest.main(verbosity=2)
