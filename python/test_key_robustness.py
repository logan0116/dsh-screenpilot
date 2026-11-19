"""按键解析健壮性测试：别名归一化、未知键拒绝、daemon 异常不致命。

对应 specs/009-keysym-robustness。
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image

import daemon
import screen_protocol
from screen_protocol import ScreenProtocol, resolve_keysym


class FakeRemote:
    """不连 VNC 的假连接：记录 tap 序列。"""

    def __init__(self, w=1080, h=1920):
        self.w = w
        self.h = h
        self.tapped = []
        self.clicks = []
        self.scrolls = []

    def snapshot(self):
        return Image.new("RGB", (self.w, self.h))

    def tap(self, keysym):
        self.tapped.append(keysym)

    def click(self, x, y):
        self.clicks.append((x, y))

    def type_text(self, text):
        self.typed = text

    def scroll(self, x, y, clicks=3, up=False):
        self.scrolls.append((x, y, clicks, up))


def make_protocol():
    remote = FakeRemote()
    sp = ScreenProtocol(remote, None, os.path.join(os.path.dirname(__file__), "evidence"))
    return sp, remote


class KeyAliasTest(unittest.TestCase):
    def test_canonical_names_resolve(self):
        self.assertEqual(resolve_keysym("enter"), 0xFF0D)
        self.assertEqual(resolve_keysym("esc"), 0xFF1B)
        self.assertEqual(resolve_keysym("pageup"), 0xFF55)
        self.assertEqual(resolve_keysym("pagedown"), 0xFF56)
        self.assertEqual(resolve_keysym("f12"), 0xFFC9)

    def test_aliases_resolve_to_same_keysym(self):
        self.assertEqual(resolve_keysym("escape"), 0xFF1B)
        self.assertEqual(resolve_keysym("ESC"), 0xFF1B)
        self.assertEqual(resolve_keysym("Esc"), 0xFF1B)
        self.assertEqual(resolve_keysym("page_up"), 0xFF55)
        self.assertEqual(resolve_keysym("page-up"), 0xFF55)
        self.assertEqual(resolve_keysym("page_down"), 0xFF56)
        self.assertEqual(resolve_keysym("page-down"), 0xFF56)
        self.assertEqual(resolve_keysym("pgup"), 0xFF55)
        self.assertEqual(resolve_keysym("pgdn"), 0xFF56)
        self.assertEqual(resolve_keysym("return"), 0xFF0D)
        self.assertEqual(resolve_keysym("spacebar"), 0x20)
        self.assertEqual(resolve_keysym("arrowup"), 0xFF52)

    def test_single_printable_char_resolves_to_codepoint(self):
        self.assertEqual(resolve_keysym("a"), ord("a"))
        self.assertEqual(resolve_keysym("7"), ord("7"))

    def test_unknown_name_returns_none(self):
        self.assertIsNone(resolve_keysym("不存在的键"))
        self.assertIsNone(resolve_keysym("hyper"))
        self.assertIsNone(resolve_keysym(""))
        self.assertIsNone(resolve_keysym(None))


class ActKeyTest(unittest.TestCase):
    def test_act_key_escape_taps_escape_keysym(self):
        sp, remote = make_protocol()
        result = sp.act("key", text="escape")
        self.assertTrue(result["ok"], result.get("error"))
        self.assertEqual(remote.tapped, [0xFF1B])

    def test_act_key_unknown_returns_protocol_error_and_sends_nothing(self):
        sp, remote = make_protocol()
        result = sp.act("key", text="hyper")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "PROTOCOL_ERROR")
        self.assertIn("hyper", result["error"]["message"])
        self.assertEqual(remote.tapped, [])

    def test_act_key_message_lists_supported_keys(self):
        sp, _ = make_protocol()
        result = sp.act("key", text="hyper")
        self.assertIn("esc", result["error"]["hint"])


class DaemonSurvivalTest(unittest.TestCase):
    def test_handle_wraps_unexpected_exception(self):
        class Exploding:
            seq = 0
            meta = {}
            remote = None

            def describe(self, **kwargs):
                raise RuntimeError("boom")

        result = daemon.handle(Exploding(), {"cmd": "describe", "args": {}})
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "PROTOCOL_ERROR")
        self.assertIn("boom", result["error"]["message"])

    def test_handle_keeps_unknown_command_as_protocol_error(self):
        class Stub:
            seq = 0
            meta = {}
            remote = None

            def _fail(self, code, message, hint=""):
                return {"ok": False, "error": {"code": code, "message": message, "hint": hint},
                        "data": {}, "capture": None, "seq": 0, "screen": {}}

        result = daemon.handle(Stub(), {"cmd": "nope", "args": {}})
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "PROTOCOL_ERROR")


class KeysymTableTest(unittest.TestCase):
    def test_table_has_no_duplicate_lowercase_keys(self):
        names = [k.lower() for k in screen_protocol.KEYSYM]
        self.assertEqual(len(names), len(set(names)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
