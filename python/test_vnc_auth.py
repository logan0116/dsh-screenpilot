"""VNC Authentication（安全类型 2）的正确性验证。

交叉验证策略，避免自证：
- DES 结果用 openssl 命令行独立算出（外部实现），与我们的 auth_response 比对；
- 密钥的比特序反转在测试里用另一种写法（字符串反转）重算；
- 握手流程用假 socket 驱动 _connect()，覆盖成功、密码错误、缺密码三种结局。
"""
import os
import shutil
import struct
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import vnc_auth
from remote_screen import RemoteScreen, VncAuthError

CHALLENGE = bytes([0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88,
                   0x99, 0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF, 0x00])


def openssl_des_ecb(key8: bytes, data: bytes) -> bytes:
    """用 openssl 独立算 DES-ECB（legacy provider），拿不到就跳过。"""
    openssl = shutil.which("openssl")
    if not openssl:
        return None
    proc = subprocess.run(
        [openssl, "enc", "-des-ecb", "-provider", "legacy", "-provider", "default",
         "-K", key8.hex(), "-nopad"],
        input=data, capture_output=True,
    )
    if proc.returncode != 0 or len(proc.stdout) != len(data):
        return None
    return proc.stdout


class KeyDerivationTest(unittest.TestCase):
    def test_key_is_bit_reversed_and_padded(self):
        raw = "password".encode()
        padded = raw[:8]
        # 用字符串反转的另一种写法重算，避免与被测实现同源
        expected = bytes(
            int("".join(reversed(format(byte, "08b"))), 2) for byte in padded
        )
        self.assertEqual(vnc_auth.des_key("password"), expected)

    def test_short_password_padded_with_zero(self):
        self.assertEqual(vnc_auth.des_key("ab")[:1], bytes([0b10000110]))  # 'a'=0x61 → 0x86
        self.assertEqual(vnc_auth.des_key("ab")[2:], b"\x00" * 6)


class DesCrossCheckTest(unittest.TestCase):
    def test_against_openssl(self):
        key = vnc_auth.des_key("s3cret!")
        expected = openssl_des_ecb(key, CHALLENGE)
        if expected is None:
            self.skipTest("openssl 不可用或未启用 legacy provider")
        self.assertEqual(vnc_auth.auth_response("s3cret!", CHALLENGE), expected)

    def test_response_is_16_bytes(self):
        self.assertEqual(len(vnc_auth.auth_response("x", CHALLENGE)), 16)


class FakeSocket:
    """按脚本喂数据，记录客户端发出的字节。"""

    def __init__(self, inbound: bytes):
        self.buf = bytearray(inbound)
        self.sent = bytearray()

    def settimeout(self, _t):
        pass

    def sendall(self, data):
        self.sent += data

    def recv(self, n):
        chunk = bytes(self.buf[:n])
        del self.buf[:n]
        if not chunk:
            raise EOFError("closed")
        return chunk

    def close(self):
        pass


def banner_and_types(types):
    return b"RFB 003.008\n" + bytes([len(types)]) + bytes(types)


class HandshakeTest(unittest.TestCase):
    def setUp(self):
        self._old_pwd = os.environ.get(vnc_auth.PASSWORD_ENV)
        os.environ.pop(vnc_auth.PASSWORD_ENV, None)

    def tearDown(self):
        if self._old_pwd is None:
            os.environ.pop(vnc_auth.PASSWORD_ENV, None)
        else:
            os.environ[vnc_auth.PASSWORD_ENV] = self._old_pwd

    def connect_with(self, inbound):
        sock = FakeSocket(inbound)
        import socket as socket_mod

        original = socket_mod.create_connection
        socket_mod.create_connection = lambda *a, **k: sock
        try:
            remote = RemoteScreen("127.0.0.1", 5900)
            remote._connect()
        finally:
            socket_mod.create_connection = original
        return sock

    def test_auth_success(self):
        os.environ[vnc_auth.PASSWORD_ENV] = "s3cret!"
        server_init = struct.pack("!HH", 8, 8) + b"\x20" * 16 + struct.pack("!I", 1) + b"x"
        inbound = (banner_and_types([2]) + CHALLENGE
                   + struct.pack("!I", 0)          # SecurityResult 成功
                   + server_init)
        sock = self.connect_with(inbound)
        self.assertIn(bytes([2]), sock.sent)                       # 选了安全类型 2
        self.assertIn(vnc_auth.auth_response("s3cret!", CHALLENGE), sock.sent)

    def test_wrong_password(self):
        os.environ[vnc_auth.PASSWORD_ENV] = "s3cret!"
        reason = b"Authentication failed"
        inbound = (banner_and_types([2]) + CHALLENGE
                   + struct.pack("!I", 1) + struct.pack("!I", len(reason)) + reason)
        with self.assertRaises(VncAuthError) as ctx:
            self.connect_with(inbound)
        self.assertIn("认证失败", str(ctx.exception))

    def test_missing_password(self):
        inbound = banner_and_types([2]) + CHALLENGE
        with self.assertRaises(VncAuthError) as ctx:
            self.connect_with(inbound)
        self.assertIn(vnc_auth.PASSWORD_ENV, str(ctx.exception))

    def test_none_auth_still_works(self):
        server_init = struct.pack("!HH", 8, 8) + b"\x20" * 16 + struct.pack("!I", 1) + b"x"
        inbound = banner_and_types([1]) + struct.pack("!I", 0) + server_init
        sock = self.connect_with(inbound)
        self.assertIn(bytes([1]), sock.sent)


if __name__ == "__main__":
    unittest.main(verbosity=2)
