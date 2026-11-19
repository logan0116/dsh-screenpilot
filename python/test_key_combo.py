"""组合键解析与发送（假 RemoteScreen，不连真机）。

覆盖 012-AR：`act(kind=key, value="ctrl+space")` 这类组合键。
- 修饰键 → 主键 → 逆序抬起，事件顺序可断言；
- 未知修饰键/未知主键/多主键在发送前拒绝，零副作用；
- 单键行为不变（仍走 tap）。
"""
import os
import sys
import tempfile
import unittest

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from screen_protocol import ScreenProtocol, parse_combo

CTRL = 0xFFE3
SHIFT = 0xFFE1
ALT = 0xFFE9


class FakeLocator:
    def scan(self, image, region=None, col_w=480):
        return []

    def scan_columns(self, image, col_w=480):
        return []

    def find(self, image, needle, region=None, min_score=0.6):
        return None

    def find_all(self, image, needle, region=None, min_score=0.6):
        return []


class FakeRemote:
    w, h = 100, 100

    def __init__(self):
        self.events = []

    def snapshot(self, attempts=3, region=None):
        return Image.new("RGB", (self.w, self.h), (0, 0, 0))

    def tap(self, keysym):
        self.events.append(("tap", keysym))

    def key_combo(self, modifiers, keysym):
        for mod in modifiers:
            self.events.append(("down", mod))
        self.events.append(("down", keysym))
        self.events.append(("up", keysym))
        for mod in reversed(modifiers):
            self.events.append(("up", mod))

    def click(self, x, y):
        self.events.append(("click", x, y))

    def type_text(self, text):
        self.events.append(("type", text))

    def scroll(self, x, y, clicks=3, up=False):
        self.events.append(("scroll", x, y, clicks, up))


def protocol_with(remote):
    return ScreenProtocol(remote, FakeLocator(), tempfile.mkdtemp(prefix="combo-"), meta={})


class ParseComboTest(unittest.TestCase):
    def test_single_key_still_plain(self):
        self.assertEqual(parse_combo("escape"), ([], 0xFF1B))

    def test_ctrl_space(self):
        mods, key = parse_combo("ctrl+space")
        self.assertEqual(mods, [CTRL])
        self.assertEqual(key, 0x20)

    def test_ctrl_shift_s(self):
        mods, key = parse_combo("Ctrl+Shift+S")
        self.assertEqual(mods, [CTRL, SHIFT])
        self.assertEqual(key, ord("s"))

    def test_win_alias(self):
        mods, _ = parse_combo("win+space")
        self.assertEqual(mods, [0xFFEB])

    def test_lone_modifier_is_a_key(self):
        # 现场用单按 Shift 切中英文，不能报"缺主键"
        self.assertEqual(parse_combo("shift"), ([], SHIFT))

    def test_unknown_key_rejected(self):
        with self.assertRaises(ValueError):
            parse_combo("ctrl+notakey")

    def test_unknown_modifier_rejected(self):
        # 只有修饰键、没有主键
        with self.assertRaises(ValueError):
            parse_combo("ctrl+alt")

    def test_two_primary_keys_rejected(self):
        with self.assertRaises(ValueError):
            parse_combo("ctrl+a+b")

    def test_empty_token_rejected(self):
        with self.assertRaises(ValueError):
            parse_combo("ctrl++a")


class ActComboTest(unittest.TestCase):
    def test_alt_f4_order(self):
        remote = FakeRemote()
        result = protocol_with(remote).act("key", text="alt+f4")
        self.assertTrue(result["ok"], result)
        self.assertEqual(remote.events, [
            ("down", ALT), ("down", 0xFFC1), ("up", 0xFFC1), ("up", ALT),
        ])

    def test_invalid_combo_has_no_side_effect(self):
        remote = FakeRemote()
        result = protocol_with(remote).act("key", text="ctrl+不存在的键")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "PROTOCOL_ERROR")
        self.assertIn("可用修饰键", result["error"]["hint"])
        self.assertEqual(remote.events, [])

    def test_single_key_uses_tap(self):
        remote = FakeRemote()
        protocol_with(remote).act("key", text="escape")
        self.assertEqual(remote.events, [("tap", 0xFF1B)])


if __name__ == "__main__":
    unittest.main(verbosity=2)
