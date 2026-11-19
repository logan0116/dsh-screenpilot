"""同帧 OCR 缓存与 describe 的 fast 模式（不连真机、不加载模型）。

覆盖 015-AR：
- 同一帧第二次查找不再识别（缓存命中）；
- 帧变了就重新识别（缓存不误命中）；
- describe 的 mode=fast 走整图单次，precise 走分列；
- describe 会把结果挂到帧上，后续 verify/act 可直接复用。
"""
import os
import sys
import tempfile
import unittest

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ocr_locator import TextLocator
from screen_protocol import ScreenProtocol

W = H = 32


class CountingLocator(TextLocator):
    """不加载模型，只数"识别了几次"。"""

    def __init__(self):
        super().__init__()
        self.scan_calls = 0
        self.column_calls = 0

    def scan(self, image, region=None, col_w=480):
        self.scan_calls += 1
        return [("目标按钮", 5, 6, 0.98), ("其它", 1, 1, 0.9)]

    def scan_columns(self, image, col_w=480):
        self.column_calls += 1
        return [("目标按钮", 5, 6, 0.98), ("其它", 1, 1, 0.9), ("小字126", 9, 9, 0.7)]


class FakeRemote:
    w, h = W, H

    def __init__(self, frames):
        self.frames = list(frames)

    def snapshot(self, attempts=3, region=None):
        return self.frames.pop(0) if self.frames else Image.new("RGB", (W, H), (0, 0, 0))


def protocol(frames):
    locator = CountingLocator()
    return ScreenProtocol(FakeRemote(frames), locator, tempfile.mkdtemp(prefix="ocr-"), meta={}), locator


class CacheTest(unittest.TestCase):
    def test_same_frame_is_cached(self):
        img = Image.new("RGB", (W, H), (10, 10, 10))
        sp, loc = protocol([img])
        sp.describe()                      # 第一次识别
        self.assertEqual(loc.column_calls, 1)
        found = loc.find(img, "目标按钮")   # 同一帧再查
        self.assertIsNotNone(found)
        self.assertEqual(loc.column_calls + loc.scan_calls, 1, "同帧不应再识别")

    def test_new_frame_reidentifies(self):
        a = Image.new("RGB", (W, H), (10, 10, 10))
        b = Image.new("RGB", (W, H), (20, 20, 20))
        sp, loc = protocol([a])
        sp.describe()
        before = loc.column_calls + loc.scan_calls
        loc.find(b, "目标按钮")
        self.assertGreater(loc.column_calls + loc.scan_calls, before, "换帧必须重新识别")

    def test_two_frames_cached_independently(self):
        a = Image.new("RGB", (W, H), (1, 1, 1))
        b = Image.new("RGB", (W, H), (2, 2, 2))
        sp, loc = protocol([a])
        sp.describe()
        self.assertIsNotNone(loc.cached(a))
        self.assertIsNone(loc.cached(b))


class ModeTest(unittest.TestCase):
    def test_fast_uses_single_pass(self):
        sp, loc = protocol([Image.new("RGB", (W, H), (0, 0, 0))])
        result = sp.describe(mode="fast")
        self.assertTrue(result["ok"])
        self.assertEqual(loc.scan_calls, 1)
        self.assertEqual(loc.column_calls, 0)
        self.assertEqual(result["data"]["mode"], "fast")

    def test_precise_uses_columns(self):
        sp, loc = protocol([Image.new("RGB", (W, H), (0, 0, 0))])
        result = sp.describe(mode="precise")
        self.assertEqual(loc.column_calls, 1)
        self.assertEqual(loc.scan_calls, 0)
        self.assertEqual(result["data"]["mode"], "precise")


if __name__ == "__main__":
    unittest.main(verbosity=2)
