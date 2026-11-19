"""截图文字定位：把 OCR 结果变成可点击的坐标。

RapidOCR 返回的坐标就是 framebuffer 像素坐标，可以直接交给
RemoteScreen.click。region 用来把识别范围限制在局部，减少耗时。
"""
import re

import numpy as np

_FULLWIDTH = str.maketrans("（）［］：，", "()[]:,")


def normalize(text):
    """去掉空白并把常见全角标点转成半角，用于宽松匹配。"""
    return re.sub(r"\s+", "", text.translate(_FULLWIDTH))


class TextLocator:
    """在一张截图上按文字查找元素坐标。

    识别引擎惰性加载：只调 start / settle 的进程不必为 OCR 付初始化成本。
    """

    def __init__(self):
        self._engine = None

    @property
    def engine(self):
        if self._engine is None:
            from rapidocr_onnxruntime import RapidOCR

            self._engine = RapidOCR()
        return self._engine

    def scan(self, image, region=None):
        """识别文字，返回 [(text, cx, cy, score), ...]。

        region 是 (x0, y0, x1, y1)，坐标仍返回原图坐标。
        """
        x0, y0 = 0, 0
        crop = image
        if region:
            x0, y0, x1, y1 = region
            crop = image.crop((x0, y0, x1, y1))
        result, _ = self.engine(np.array(crop))
        items = []
        for box, text, score in result or []:
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            cx = int(sum(xs) / 4) + x0
            cy = int(sum(ys) / 4) + y0
            items.append((text.strip(), cx, cy, float(score)))
        return items

    def find(self, image, needle, region=None, min_score=0.6):
        """按子串找第一个匹配项，返回 (cx, cy) 或 None。"""
        want = normalize(needle)
        for text, cx, cy, score in self.scan(image, region):
            if score >= min_score and want in normalize(text):
                return cx, cy
        return None

    def scan_columns(self, image, col_w=480):
        """按列切分扫描：小字号在全图检测里容易被漏掉，分列后能恢复。"""
        width, height = image.size
        items = []
        for x0 in range(0, width, col_w):
            x1 = min(x0 + col_w, width)
            items.extend(self.scan(image, (x0, 0, x1, height)))
        return items

    def find_all(self, image, needle, region=None, min_score=0.6):
        """按子串找全部匹配项；全图漏检时自动退化为分列扫描。"""
        want = normalize(needle)

        def match(items):
            exact, partial = [], []
            for text, cx, cy, score in items:
                if score < min_score:
                    continue
                norm = normalize(text)
                if norm == want:
                    exact.append((cx, cy, text))
                elif want in norm:
                    partial.append((cx, cy, text))
            return exact + partial

        if region:
            return match(self.scan(image, region))
        hits = match(self.scan(image))
        if hits:
            return hits
        return match(self.scan_columns(image))
