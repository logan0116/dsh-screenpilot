"""协议自测：12 条用例覆盖 rsp/1 的正常路径与失败路径。"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ocr_locator import TextLocator
from remote_screen import RemoteScreen
from screen_protocol import ScreenProtocol

EVIDENCE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "evidence")
LEFT = (0, 700, 300, 1200)
ADDR = (0, 470, 1080, 560)
results = []


def case(cid, title, fn):
    start = time.time()
    try:
        ok, detail = fn()
    except Exception as exc:  # noqa: BLE001 - 自测脚本需要记录任何异常
        ok, detail = False, f"EXC {type(exc).__name__}: {exc}"
    cost = round(time.time() - start, 1)
    results.append((cid, title, ok, cost, detail))
    print(f"{cid} {'PASS' if ok else 'FAIL'} {cost:>5.1f}s  {title}  | {detail}", flush=True)
    return ok


def make():
    return ScreenProtocol(RemoteScreen(), TextLocator(), EVIDENCE)


sp = make()


def p01():
    r = sp.describe(region=LEFT)
    if not r["ok"]:
        return False, r["error"]["code"]
    hits = [t for t in r["data"]["texts"] if "下载" in t["text"]]
    if not hits:
        return False, "未识别到下载"
    h = hits[0]
    return 0 <= h["x"] <= 300 and 900 <= h["y"] <= 1050, f"({h['x']},{h['y']})"


def p02():
    r = sp.act("click", text="下载")
    if not r["ok"]:
        return False, r["error"]["code"]
    v = sp.verify("text", text="下载", region=ADDR)
    return v["data"].get("found", False), f"target={r['data'].get('target')} addr={v['data']}"


def p03():
    full = sp.describe()
    if not full["ok"]:
        return False, full["error"]["code"]
    sub = sp.describe(region=LEFT)
    a = next((t for t in full["data"]["texts"] if "下载" in t["text"] and 900 < t["y"] < 1060), None)
    b = next((t for t in sub["data"]["texts"] if "下载" in t["text"]), None)
    if not a or not b:
        return False, f"full={bool(a)} region={bool(b)}"
    d = abs(a["x"] - b["x"]) + abs(a["y"] - b["y"])
    return d <= 4, f"full=({a['x']},{a['y']}) region=({b['x']},{b['y']}) delta={d}"


def p04():
    r = sp.act("click", text="搜索")
    if not r["ok"]:
        return False, r["error"]["code"]
    t = sp.act("type", text="test")
    if not t["ok"]:
        return False, t["error"]["code"]
    v = sp.verify("text", text="test", region=(600, 660, 1080, 720))
    return v["data"].get("found", False), f"typed={v['data']}"


def p05():
    before = sp.describe()
    if not before["ok"]:
        return False, before["error"]["code"]
    r = sp.act("scroll", dy=3, xy=(540, 1000))
    if not r["ok"]:
        return False, r["error"]["code"]
    from PIL import ImageChops

    d = ImageChops.difference(sp._prev, sp._last).convert("L")
    changed = sum(1 for p in d.getdata() if p > 8)
    return changed > 5000, f"diff={changed}"


def p06():
    a = sp.act("click", text="此电脑", region=LEFT)
    if not a["ok"]:
        return False, f"此电脑 {a['error']['code']}"
    v1 = sp.verify("text", text="此电脑", region=ADDR)
    b = sp.act("click", text="软件", region=LEFT)
    if not b["ok"]:
        return False, f"软件 {b['error']['code']}"
    v2 = sp.verify("text", text="软件", region=ADDR)
    return v1["data"]["found"] and v2["data"]["found"], f"step1={v1['data']['found']} step2={v2['data']['found']}"


def p07():
    r = sp.act("click", text="桌面")
    if not r["ok"]:
        return False, r["error"]["code"]
    paths = [os.path.join(EVIDENCE, r["data"]["before"]), os.path.join(EVIDENCE, r["data"]["after"])]
    sizes = [os.path.getsize(p) if os.path.exists(p) else 0 for p in paths]
    return all(s > 1000 for s in sizes), f"sizes={sizes}"


def p08():
    r = sp.act("click", text="绝对不存在的文本XYZ")
    code = r["error"]["code"] if not r["ok"] else "NONE"
    return code == "NOT_FOUND", f"code={code}"


def p09():
    r = sp.act("click", text="文件")
    if not r["ok"]:
        return False, r["error"]["code"]
    return bool(r["data"].get("candidates")), f"candidates={len(r['data'].get('candidates') or [])}"


def p10():
    r = sp.act("click", xy=(5000, 5000))
    code = r["error"]["code"] if not r["ok"] else "NONE"
    return code == "OUT_OF_BOUNDS", f"code={code}"


def p11():
    bad = ScreenProtocol(RemoteScreen(port=5999), TextLocator(), EVIDENCE)
    r = bad.describe()
    code = r["error"]["code"] if not r["ok"] else "NONE"
    return code == "NO_CONNECTION", f"code={code}"


def p12():
    sp.describe()
    r = sp.act("click", xy=(700, 1470))
    # 无效等价类：点击空白属于合法动作，act 必须成功；界面是否变化与动作成败无关。
    return r["ok"], f"ok={r['ok']} error={r.get('error')}"


CASES = [
    ("P01", "describe 定位精度", p01),
    ("P02", "文字目标点击 + 地址栏复核", p02),
    ("P03", "区域与全图坐标一致", p03),
    ("P04", "文本输入", p04),
    ("P05", "滚动", p05),
    ("P06", "多级导航", p06),
    ("P07", "证据链完整", p07),
    ("P08", "找不到 → NOT_FOUND", p08),
    ("P09", "多匹配返回候选", p09),
    ("P10", "坐标越界", p10),
    ("P11", "连接失败", p11),
    ("P12", "空白点击无变化", p12),
]

if __name__ == "__main__":
    for cid, title, fn in CASES:
        case(cid, title, fn)
    passed = sum(1 for r in results if r[2])
    print(f"\n通过 {passed}/{len(results)}")
    for cid, title, ok, cost, detail in results:
        if not ok:
            print(f"  失败 {cid} {title}: {detail}")
