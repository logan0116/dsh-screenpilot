"""settle 的区域判稳与容差（假 RemoteScreen，不连真机）。

覆盖 011-AR：
- region 只比较关注区域，期间画面其它区域发生变化也算稳定；
- 差异像素占比低于 tolerance 判稳定，回 changedRatio；
- 超时不再只回 TIMEOUT：带最后一帧证据与 changedRatio；
- region 越界返回 OUT_OF_BOUNDS（由 remote 抛 ValueError 转换）。
"""
import os
import sys
import tempfile
import unittest

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from screen_protocol import ScreenProtocol


class FakeLocator:
    """settle 不用 OCR，占位即可。"""

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

    def __init__(self, frames):
        self.frames = list(frames)
        self.calls = []
        self.count = 0

    def snapshot(self, attempts=3, region=None):
        self.calls.append(region)
        if region:
            x0, y0, x1, y1 = region
            if not (0 <= x0 < x1 <= self.w and 0 <= y0 < y1 <= self.h):
                raise ValueError(f"region {region} 超出 {self.w}x{self.h}")
            self.asserted = True
        frame = self.frames[self.count % len(self.frames)]
        self.count += 1
        if region:
            frame = frame.crop((x0, y0, x1, y1))
        return frame


def solid(color, size=(100, 100)):
    return Image.new("RGB", size, color)


def with_noise(size=(100, 100)):
    img = solid((0, 0, 0), size)
    for x in range(0, size[0], 2):
        img.putpixel((x, 0), (255, 255, 255))
    return img


class SettleRegionTest(unittest.TestCase):
    def setUp(self):
        self.evidence = tempfile.mkdtemp(prefix="settle-evidence-")

    def protocol(self, frames):
        return ScreenProtocol(FakeRemote(frames), FakeLocator(), self.evidence, meta={})

    def test_region_ignores_change_outside(self):
        # 区域外全黑与全白，区域内始终红色 → 应在区域内判稳
        region = (10, 10, 30, 30)
        a = solid((0, 0, 0))
        b = solid((255, 255, 255))
        a.paste(solid((255, 0, 0), (20, 20)), (10, 10))
        b.paste(solid((255, 0, 0), (20, 20)), (10, 10))
        result = self.protocol([a, b]).settle(timeout=1, quiet=0.01, region=region)
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["data"]["stable"])
        self.assertLessEqual(result["data"]["changedRatio"], 0.002)
        self.assertEqual(result["data"]["region"], list(region))

    def test_changing_region_times_out_with_ratio(self):
        region = (0, 0, 100, 100)
        frames = [solid((i * 20 % 256, 0, 0)) for i in range(1, 40)]
        result = self.protocol(frames).settle(timeout=0.2, quiet=0.01, region=region)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "TIMEOUT")
        self.assertIsNotNone(result["data"]["changedRatio"])
        self.assertGreater(result["data"]["changedRatio"], 0.002)
        self.assertTrue(result["capture"], "超时也要留下最后一帧证据")

    def test_tolerance_controls_stability(self):
        region = (0, 0, 100, 100)
        # 每次只变 1% 的像素：默认 0.2% 判不稳，容忍 2% 判稳
        base = solid((0, 0, 0))
        frames = [base, with_noise()]
        strict = self.protocol(frames).settle(timeout=0.2, quiet=0.01, region=region)
        self.assertFalse(strict["ok"])
        loose = self.protocol([base, with_noise()]).settle(
            timeout=0.5, quiet=0.01, region=region, tolerance=0.05
        )
        self.assertTrue(loose["ok"], loose)
        self.assertTrue(loose["data"]["stable"])

    def test_region_out_of_bounds(self):
        result = self.protocol([solid((0, 0, 0))]).settle(timeout=0.3, region=(50, 50, 200, 200))
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "OUT_OF_BOUNDS")

    def test_region_only_requests_region(self):
        remote = FakeRemote([solid((0, 0, 0))])
        ScreenProtocol(remote, FakeLocator(), self.evidence, meta={}).settle(
            timeout=0.3, quiet=0.01, region=(1, 2, 11, 22)
        )
        self.assertTrue(remote.calls)
        self.assertTrue(all(call == (1, 2, 11, 22) for call in remote.calls), remote.calls)


if __name__ == "__main__":
    unittest.main(verbosity=2)
