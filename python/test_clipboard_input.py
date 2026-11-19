"""剪贴板通道输入非 ASCII（假 RemoteScreen，不连真机）。

覆盖 018-AR：
- 非 ASCII 文本默认走剪贴板：先 ClientCutText 写远端剪贴板，再发 Ctrl+V；
- input_mode=keysym 时维持 007 的行为（UNSUPPORTED，零副作用）；
- input_mode=clipboard 强制走剪贴板；
- 信封 data.input_mode 标明实际通道。
"""
import os
import sys
import tempfile
import unittest

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from remote_screen import RemoteScreen
from screen_protocol import ScreenProtocol

CTRL = 0xFFE3


class FakeLocator:
    def scan(self, image, region=None, col_w=480):
        return []

    def scan_columns(self, image, col_w=480):
        return []

    def find(self, image, needle, region=None, min_score=0.6):
        return None

    def find_all(self, image, needle, region=None, min_score=0.6):
        return [(1, 1, needle)] if needle else []


class FakeRemote:
    w, h = 40, 40

    def __init__(self):
        self.events = []

    def snapshot(self, attempts=3, region=None):
        return Image.new("RGB", (self.w, self.h), (0, 0, 0))

    def set_clipboard(self, text):
        self.events.append(("clipboard", text))

    def key_combo(self, modifiers, keysym):
        self.events.append(("combo", tuple(modifiers), keysym))

    def type_text(self, text):
        self.events.append(("type", text))

    def click(self, x, y):
        self.events.append(("click", x, y))

    def scroll(self, x, y, clicks=3, up=False):
        self.events.append(("scroll", x, y))


def protocol():
    remote = FakeRemote()
    return ScreenProtocol(remote, FakeLocator(), tempfile.mkdtemp(prefix="clip-"), meta={}), remote


class ClipboardInputTest(unittest.TestCase):
    def test_non_ascii_defaults_to_clipboard(self):
        sp, remote = protocol()
        result = sp.act("type", text="中文配置", wait=0)
        self.assertTrue(result["ok"], result)
        self.assertIn(("clipboard", "中文配置"), remote.events)
        self.assertIn(("combo", (CTRL,), ord("v")), remote.events)
        self.assertEqual(result["data"]["input_mode"], "clipboard")

    def test_ascii_still_uses_keysym(self):
        sp, remote = protocol()
        result = sp.act("type", text="abc123", wait=0)
        self.assertTrue(result["ok"], result)
        self.assertIn(("type", "abc123"), remote.events)
        self.assertEqual(result["data"]["input_mode"], "keysym")

    def test_keysym_mode_rejects_non_ascii(self):
        sp, remote = protocol()
        result = sp.act("type", text="中文", wait=0, input_mode="keysym")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "UNSUPPORTED")
        self.assertEqual([e for e in remote.events if e[0] in ("clipboard", "combo")], [])

    def test_explicit_clipboard_for_ascii(self):
        sp, remote = protocol()
        result = sp.act("type", text="abc", wait=0, input_mode="clipboard")
        self.assertTrue(result["ok"], result)
        self.assertIn(("clipboard", "abc"), remote.events)

    def test_unknown_mode(self):
        sp, _ = protocol()
        result = sp.act("type", text="中文", wait=0, input_mode="bogus")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "PROTOCOL_ERROR")


class ClientCutTextTest(unittest.TestCase):
    def test_message_layout(self):
        sent = []
        remote = RemoteScreen("127.0.0.1", 5900)
        remote._run = lambda fn: fn(type("S", (), {"sendall": staticmethod(lambda data: sent.append(data))})())
        remote.set_clipboard("你好")
        self.assertEqual(len(sent), 1)
        payload = sent[0]
        self.assertEqual(payload[0], 6, "消息类型应为 ClientCutText(6)")
        self.assertEqual(payload[1:4], b"\x00\x00\x00", "3 字节填充")
        length = int.from_bytes(payload[4:8], "big")
        self.assertEqual(len(payload[8:]), length)
        self.assertEqual(payload[8:].decode("utf-8"), "你好")


if __name__ == "__main__":
    unittest.main(verbosity=2)
