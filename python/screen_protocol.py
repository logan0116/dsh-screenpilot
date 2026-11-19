"""屏幕能力协议（rsp/1）的最小实现。

协议只负责原子能力：取画面、按文字定位、执行输入、断言、等待稳定。
它不知道测试用例是什么，也不做用例判定。
"""
import os
import time

from PIL import ImageChops

from ocr_locator import normalize
from remote_screen import UnsupportedFeature

CODES = (
    "NO_CONNECTION",
    "NOT_STARTED",
    "UNSTABLE",
    "NOT_FOUND",
    "UNSUPPORTED",
    "OUT_OF_BOUNDS",
    "TIMEOUT",
    "PROTOCOL_ERROR",
)

KEYSYM = {
    "enter": 0xFF0D,
    "esc": 0xFF1B,
    "tab": 0xFF09,
    "backspace": 0xFF08,
    "win": 0xFFEB,
    "up": 0xFF52,
    "down": 0xFF54,
    "left": 0xFF51,
    "right": 0xFF53,
    "f5": 0xFFC2,
    "f1": 0xFFBE, "f2": 0xFFBF, "f3": 0xFFC0, "f4": 0xFFC1,
    "f6": 0xFFC3, "f7": 0xFFC4, "f8": 0xFFC5, "f9": 0xFFC6,
    "f10": 0xFFC7, "f11": 0xFFC8, "f12": 0xFFC9,
    "home": 0xFF50, "end": 0xFF57, "insert": 0xFF63, "delete": 0xFF9F,
    "pageup": 0xFF55, "pagedown": 0xFF56, "space": 0x20,
    "ctrl": 0xFFE3, "alt": 0xFFE9, "shift": 0xFFE1,
}


class ScreenProtocol:
    """把 RemoteScreen 和 TextLocator 包成协议化的调用。"""

    def __init__(self, remote, locator, evidence_dir, meta=None):
        self.remote = remote
        self.locator = locator
        self.evidence_dir = evidence_dir
        self.meta = dict(meta or {})
        os.makedirs(evidence_dir, exist_ok=True)
        self.seq = 0
        self._last = None

    def _envelope(self, ok, capture=None, data=None, error=None):
        self.seq += 1
        screen = dict(self.meta)
        screen.update({"w": self.remote.w, "h": self.remote.h})
        return {
            "ok": ok,
            "seq": self.seq,
            "screen": screen,
            "capture": capture,
            "data": data or {},
            "error": error,
        }

    def _fail(self, code, message, hint="", **extra):
        if code not in CODES:
            code = "PROTOCOL_ERROR"
        err = {"code": code, "message": message, "hint": hint}
        err.update(extra)
        return self._envelope(False, error=err)

    def _save(self, image, tag):
        name = f"{int(time.time() * 1000)}_{tag}.png"
        path = os.path.join(self.evidence_dir, name)
        image.save(path)
        return name

    def describe(self, region=None, fresh=True):
        """取画面并返回文字清单。"""
        try:
            image = self.remote.snapshot()
        except UnsupportedFeature as exc:
            return self._fail("UNSUPPORTED", str(exc),
                              "认证需 005-AR；编码类问题请在服务端关闭 Tight/ZRLE 或改用 Raw/CopyRect")
        except OSError as exc:
            return self._fail("NO_CONNECTION", str(exc), "确认测试台在线且 VNC 端口可达")
        ref = self._save(image, "describe")
        self._prev = self._last
        self._last = image
        items = (
            self.locator.scan(image, region) if region else self.locator.scan_columns(image)
        )
        texts = [
            {"text": t, "x": x, "y": y, "score": round(s, 3)} for t, x, y, s in items
        ]
        return self._envelope(True, ref, {"texts": texts, "region": region})

    def act(self, kind, text=None, xy=None, region=None, **kwargs):
        """执行一个输入动作，返回动作前后两帧证据。"""
        before = self._last
        if before is None:
            try:
                before = self.remote.snapshot()
            except UnsupportedFeature as exc:
                return self._fail("UNSUPPORTED", str(exc),
                                  "认证需 005-AR；编码类问题请在服务端关闭 Tight/ZRLE 或改用 Raw/CopyRect")
            except OSError as exc:
                return self._fail("NO_CONNECTION", str(exc))
        before_ref = self._save(before, f"{kind}_before")

        target = None
        candidates = []
        if kind == "click":
            if text:
                hits = self.locator.find_all(before, text, region=region)
                if not hits:
                    return self._fail(
                        "NOT_FOUND",
                        f"未找到文本「{text}」",
                        "尝试换关键词、扩大区域或先滚动",
                    )
                candidates = [{"text": t, "x": x, "y": y} for x, y, t in hits]
                target = {"x": hits[0][0], "y": hits[0][1], "text": hits[0][2]}
            elif xy:
                target = {"x": xy[0], "y": xy[1]}
            else:
                return self._fail("PROTOCOL_ERROR", "click 需要 text 或 xy")

        if target and (
            not (0 <= target["x"] < self.remote.w) or not (0 <= target["y"] < self.remote.h)
        ):
            return self._fail(
                "OUT_OF_BOUNDS",
                f"坐标 ({target['x']},{target['y']}) 超出 {self.remote.w}x{self.remote.h}",
            )

        if kind == "type":
            bad = next((c for c in (text or "") if (ord(c) > 0x7E or ord(c) < 0x20)
                        and c not in "\n\t"), None)
            if bad is not None:
                return self._fail(
                    "UNSUPPORTED",
                    f"非 ASCII 字符 {bad!r} (U+{ord(bad):04X}) 无法输入",
                    "当前输入通道只支持 ASCII；中文等需剪贴板注入（另立需求）",
                )

        try:
            if kind == "click":
                self.remote.click(target["x"], target["y"])
            elif kind == "type":
                self.remote.type_text(text or "")
            elif kind == "key":
                self.remote.tap(KEYSYM[(text or "").lower()])
            elif kind == "scroll":
                dy = kwargs.get("dy", 0)
                cx = target["x"] if target else self.remote.w // 2
                cy = target["y"] if target else self.remote.h // 2
                self.remote.scroll(cx, cy, clicks=abs(dy) or 3, up=dy < 0)
            else:
                return self._fail("PROTOCOL_ERROR", f"未知动作 {kind}")
        except OSError as exc:
            return self._fail("NO_CONNECTION", str(exc))

        time.sleep(1.2)
        try:
            after = self.remote.snapshot()
        except UnsupportedFeature as exc:
            return self._fail("UNSUPPORTED", str(exc),
                              "认证需 005-AR；编码类问题请在服务端关闭 Tight/ZRLE 或改用 Raw/CopyRect")
        except OSError as exc:
            return self._fail("NO_CONNECTION", str(exc))
        after_ref = self._save(after, f"{kind}_after")
        self._prev = before
        self._last = after

        data = {"before": before_ref, "after": after_ref}
        if target:
            data["target"] = target
        if len(candidates) > 1:
            data["ambiguous"] = True
            data["candidates"] = candidates
        return self._envelope(True, after_ref, data)

    @staticmethod
    def _url_core(value):
        """URL 归一化：去空白、全角转半角、小写、去 scheme。"""
        return normalize(value or "").lower().removeprefix("https://").removeprefix("http://")

    def verify(self, kind="text", text=None, region=None, min_diff=500):
        """断言。kind: text / absent / url / changed / same。"""
        image = self._last
        if image is None:
            got = self.describe()
            if not got["ok"]:
                return got
            image = self._last
        ref = self._save(image, "verify")
        if kind == "text":
            pos = self.locator.find(image, text, region=region)
            return self._envelope(True, ref, {"kind": kind, "text": text, "found": pos is not None})
        if kind == "absent":
            pos = self.locator.find(image, text, region=region)
            return self._envelope(True, ref, {"kind": kind, "text": text, "absent": pos is None})
        if kind == "url":
            want = self._url_core(text)
            if not want:
                return self._fail("PROTOCOL_ERROR", "url 断言需要 value", "传 URL 片段，如 192.168.1.155:8090")
            seen = self.locator.scan(image, region) if region else self.locator.scan(image)
            hits = [t for t, _x, _y, _s in seen if want in self._url_core(t)]
            if hits:
                return self._envelope(True, ref, {"kind": kind, "text": text, "satisfied": True, "hits": hits[:3]})
            # 画面里根本没有 URL 形态文本：vnc 后端无从判断地址栏，交回 UNSUPPORTED
            if not any("://" in t for t, _x, _y, _s in seen):
                return self._fail(
                    "UNSUPPORTED",
                    f"画面中没有可识别的地址栏或 URL 文本，无法断言「{text}」",
                    "vnc 后端只能按画面文字判断；确认地址栏可见，或改用 kind=text",
                )
            return self._envelope(True, ref, {"kind": kind, "text": text, "satisfied": False})

        if kind == "changed":
            prev = getattr(self, "_prev", None)
            if prev is None:
                return self._fail("PROTOCOL_ERROR", "没有可比的前一帧")
            d = ImageChops.difference(prev, image).convert("L")
            changed = sum(1 for p in d.getdata() if p > 8)
            self._prev = image
            return self._envelope(True, ref, {"kind": kind, "diff": changed, "changed": changed >= min_diff})
        return self._fail("PROTOCOL_ERROR", f"未知断言 {kind}")

    def settle(self, timeout=8.0, quiet=0.6):
        """等到画面连续两次快照一致。"""
        deadline = time.time() + timeout
        prev = None
        while time.time() < deadline:
            try:
                image = self.remote.snapshot()
            except UnsupportedFeature as exc:
                return self._fail("UNSUPPORTED", str(exc),
                                  "认证需 005-AR；编码类问题请在服务端关闭 Tight/ZRLE 或改用 Raw/CopyRect")
            except OSError as exc:
                return self._fail("NO_CONNECTION", str(exc), "确认测试台在线且 VNC 端口可达")
            if prev is not None and image.tobytes() == prev.tobytes():
                self._last = image
                ref = self._save(image, "settle")
                return self._envelope(True, ref, {"stable": True})
            prev = image
            time.sleep(quiet)
        return self._fail("TIMEOUT", f"{timeout}s 内画面未稳定", "确认界面没有持续动画或后台刷新")
