"""screen_* 能力的命令行入口：一次调用一个动作，输出 JSON。

目标解析在 session.py：显式 --target > 会话文件 > --default > 内置缺省。
start 成功才写会话文件，后续命令据此连同一台台架。
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import session as target_session
from ocr_locator import TextLocator
from remote_screen import RemoteScreen
from screen_protocol import ScreenProtocol

EVIDENCE = os.environ.get("SCREENPILOT_EVIDENCE") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "evidence"
)


def fail(code, message, hint=""):
    return {
        "ok": False,
        "seq": 0,
        "screen": {},
        "capture": None,
        "data": {},
        "error": {"code": code, "message": message, "hint": hint},
    }


def parse_region(text):
    if not text:
        return None
    parts = [int(v) for v in text.split(",")]
    if len(parts) != 4:
        raise SystemExit("region 格式为 x0,y0,x1,y1")
    return tuple(parts)


def build(host, port, source):
    return ScreenProtocol(
        RemoteScreen(host, port),
        TextLocator(),
        EVIDENCE,
        meta={"host": host, "port": port, "source": source},
    )


def execute(args, host, port, source):
    sp = build(host, port, source)
    region = parse_region(args.region)

    if args.command == "start":
        result = sp.settle(timeout=args.timeout)
        if not result["ok"]:
            return result
        try:
            target_session.save_session(host, port)
        except OSError as exc:
            result["data"]["state_warning"] = f"会话文件写入失败：{exc}"
        result["session"] = "default"
        result["capabilities"] = ["text", "xy"]
        return result

    if args.command == "describe":
        return sp.describe(region=region)
    if args.command == "settle":
        return sp.settle(timeout=args.timeout)
    if args.command == "verify":
        return sp.verify(kind=args.kind, text=args.text, region=region)

    xy = tuple(int(v) for v in args.xy.split(",")) if args.xy else None
    return sp.act(args.kind, text=args.text, xy=xy, region=region, dy=args.dy)


def main(argv=None):
    parser = argparse.ArgumentParser(description="远程屏幕能力 CLI（rsp/2）")
    parser.add_argument("command", choices=["start", "describe", "act", "verify", "settle"])
    parser.add_argument("--target", help="vnc://host[:port]，缺省用会话文件或 --default")
    parser.add_argument("--default", help="兜底目标，通常是插件配置的 defaultTarget")
    parser.add_argument("--kind", default="click", help="click/type/key/scroll，或 verify 的断言类型")
    parser.add_argument("--text")
    parser.add_argument("--xy")
    parser.add_argument("--region")
    parser.add_argument("--dy", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=8.0)
    args = parser.parse_args(argv)

    try:
        host, port, source = target_session.resolve(args.target, args.default)
    except target_session.UnsupportedTarget as exc:
        result = fail("UNSUPPORTED", str(exc), "web 后端待接入；当前请给 vnc://host:port")
    except target_session.TargetError as exc:
        result = fail("PROTOCOL_ERROR", str(exc), "格式 vnc://host[:port]，端口缺省 5900")
    else:
        try:
            result = execute(args, host, port, source)
        except OSError as exc:
            result = fail("NO_CONNECTION", str(exc), "确认测试台在线且 VNC 端口可达")
        except KeyError as exc:
            result = fail("PROTOCOL_ERROR", f"不支持的按键：{exc}", "先确认按键名在映射表内")

    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
