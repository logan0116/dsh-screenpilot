"""常驻 sidecar：一个目标一个进程，通过 Unix domain socket 收发 rsp 调用。

进程内只持有一个 ScreenProtocol 实例，因此 `_last`/`_prev`/`seq` 跨请求存活。
"""
import argparse
import json
import os
import socket
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ocr_locator import TextLocator
from remote_screen import RemoteScreen
from screen_protocol import ScreenProtocol

DEFAULT_IDLE = 600.0


def _envelope(sp, data=None, ok=True):
    screen = dict(sp.meta)
    screen.update({"w": sp.remote.w, "h": sp.remote.h})
    return {"ok": ok, "seq": sp.seq, "screen": screen, "capture": None, "data": data or {}, "error": None}


def _fail_envelope(sp, message, hint=""):
    """不依赖 sp 状态也能构造的失败信封（sp 本身出错时仍可回包）。"""
    try:
        screen = dict(getattr(sp, "meta", {}) or {})
        remote = getattr(sp, "remote", None)
        if remote is not None:
            screen.update({"w": remote.w, "h": remote.h})
        seq = getattr(sp, "seq", 0)
    except Exception:  # noqa: BLE001 - 兜底路径，取不到就回最小信封
        screen, seq = {}, 0
    return {"ok": False, "seq": seq, "screen": screen, "capture": None,
            "data": {}, "error": {"code": "PROTOCOL_ERROR", "message": message, "hint": hint}}


def handle(sp, req):
    """执行一个请求，返回信封；任何异常都转成 PROTOCOL_ERROR，不拖垮常驻进程。"""
    try:
        return _handle(sp, req)
    except Exception as exc:  # noqa: BLE001 - 单请求失败不能终止 daemon
        import traceback

        traceback.print_exc(file=sys.stderr)
        return _fail_envelope(
            sp,
            f"{type(exc).__name__}: {exc}",
            "请求参数或状态异常；进程仍存活，可修正参数后重试",
        )


def _handle(sp, req):
    """执行一个请求，返回信封。未知命令按 PROTOCOL_ERROR 处理。"""
    cmd = req.get("cmd")
    args = req.get("args") or {}
    started = time.time()

    if cmd == "describe":
        region = args.get("region")
        result = sp.describe(region=tuple(region) if region else None)
    elif cmd == "act":
        result = sp.act(
            args.get("kind", "click"),
            text=args.get("text"),
            xy=tuple(args["xy"]) if args.get("xy") else None,
            region=tuple(args["region"]) if args.get("region") else None,
            dy=args.get("dy", 3),
        )
    elif cmd == "verify":
        region = args.get("region")
        result = sp.verify(
            kind=args.get("kind", "text"),
            text=args.get("text"),
            region=tuple(region) if region else None,
        )
    elif cmd == "frame":
        result = sp.frame(scale=args.get("scale", 0.5), quality=args.get("quality", 60))
    elif cmd == "settle":
        region = args.get("region")
        result = sp.settle(
            timeout=args.get("timeout", 8.0),
            region=tuple(region) if region else None,
            tolerance=args.get("tolerance", 0.002),
        )
    elif cmd == "ping":
        result = _envelope(sp, {"alive": True})
    elif cmd in ("stop", "shutdown"):
        result = _envelope(sp, {"stopped": True})
    else:
        result = sp._fail("PROTOCOL_ERROR", f"未知命令 {cmd!r}", "命令集合：describe/act/verify/settle/ping/shutdown")

    result["screen"]["pid"] = os.getpid()
    result["screen"]["cost"] = int((time.time() - started) * 1000)
    return result


def serve(host, port, evidence, sock_path, idle_timeout):
    sp = ScreenProtocol(
        RemoteScreen(host, port),
        TextLocator(),
        evidence,
        meta={"host": host, "port": port, "source": "daemon"},
    )
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    if os.path.exists(sock_path):
        os.unlink(sock_path)
    server.bind(sock_path)
    server.listen(8)
    server.settimeout(1.0)
    last_active = time.time()
    try:
        while True:
            try:
                conn, _ = server.accept()
            except socket.timeout:
                if time.time() - last_active > idle_timeout:
                    break
                continue
            with conn:
                buffer = b""
                while not buffer.endswith(b"\n"):
                    chunk = conn.recv(65536)
                    if not chunk:
                        break
                    buffer += chunk
                try:
                    req = json.loads(buffer.decode() or "{}")
                except json.JSONDecodeError:
                    req = {"cmd": "__bad__"}
                result = handle(sp, req)
                conn.sendall(json.dumps(result, ensure_ascii=False).encode() + b"\n")
            last_active = time.time()
            if req.get("cmd") in ("stop", "shutdown"):
                break
    finally:
        server.close()
        try:
            os.unlink(sock_path)
        except OSError:
            pass


def main(argv=None):
    parser = argparse.ArgumentParser(description="screenpilot 常驻 sidecar")
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", required=True, type=int)
    parser.add_argument("--socket", required=True)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--idle", type=float, default=DEFAULT_IDLE)
    args = parser.parse_args(argv)
    serve(args.host, args.port, args.evidence, args.socket, args.idle)
    return 0


if __name__ == "__main__":
    sys.exit(main())
