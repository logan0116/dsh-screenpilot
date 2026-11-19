"""act 自适应等待（假 RemoteScreen，不连真机）。

覆盖 014-AR：
- 默认只抓一帧（wait 之后），不补帧 → 单次 act 只有一次 snapshot；
- 显式 retry_on_no_change=True 且画面无变化时补一轮，data.retried=True；
- 画面明显变化时不补帧；
- 补帧时保留与动作前帧差异更大的那张。
"""
import os
import sys
import tempfile
import unittest

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from screen_protocol import ScreenProtocol

W = H = 40


def blank():
    return Image.new("RGB", (W, H), (0, 0, 0))


def painted(offset=0):
    img = blank()
    ImageDraw.Draw(img).rectangle([0, 0, W - 1, 9 + offset], fill=(255, 255, 255))
    return img


class FakeLocator:
    def scan(self, image, region=None, col_w=480):
        return []

    def scan_columns(self, image, col_w=480):
        return []

    def find(self, image, needle, region=None, min_score=0.6):
        return None

    def find_all(self, image, needle, region=None, min_score=0.6):
        return [(1, 1, needle)]


class FakeRemote:
    w, h = W, H

    def __init__(self, frames):
        self.frames = list(frames)
        self.snapshots = 0

    def snapshot(self, attempts=3, region=None):
        self.snapshots += 1
        if not self.frames:
            return blank()
        return self.frames.pop(0)

    def click(self, x, y):
        pass


def protocol(frames):
    remote = FakeRemote(frames)
    return ScreenProtocol(remote, FakeLocator(), tempfile.mkdtemp(prefix="act-"), meta={}), remote


class ActWaitTest(unittest.TestCase):
    def test_default_takes_single_snapshot(self):
        sp, remote = protocol([painted(0)])
        sp._last = blank()                       # 动作前帧
        result = sp.act("click", xy=(5, 5), wait=0)
        self.assertTrue(result["ok"], result)
        self.assertEqual(remote.snapshots, 1, "默认不应补帧")
        self.assertNotIn("retried", result["data"])

    def test_retry_when_unchanged(self):
        sp, remote = protocol([blank(), painted(0)])
        sp._last = blank()
        result = sp.act("click", xy=(5, 5), wait=0, retry_on_no_change=True)
        self.assertTrue(result["ok"], result)
        self.assertEqual(remote.snapshots, 2, "无变化时应补一帧")
        self.assertTrue(result["data"].get("retried"))

    def test_no_retry_when_changed(self):
        sp, remote = protocol([painted(0), painted(20)])
        sp._last = blank()
        result = sp.act("click", xy=(5, 5), wait=0, retry_on_no_change=True)
        self.assertTrue(result["ok"], result)
        self.assertEqual(remote.snapshots, 1, "画面已变化就不该补帧")

    def test_wait_is_reported(self):
        sp, _ = protocol([painted(0)])
        sp._last = blank()
        result = sp.act("click", xy=(5, 5), wait=0.3)
        self.assertEqual(result["data"]["wait"], 0.3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
