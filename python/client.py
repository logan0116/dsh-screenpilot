"""常驻 sidecar 的客户端：按需拉起、发一个请求、收一个信封。

拉起用文件锁串行化，避免并发冷启动时起出两个进程；socket 残留但进程已死时先清理。
"""
import json
import os
import socket
import subprocess
import sys
import time

import session as target_session

DAEMON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "daemon.py")
SPAWN_TIMEOUT = 15.0


class DaemonError(RuntimeError):
    """常驻进程不可用（拉起失败、超时、无响应）。"""


def socket_path(host, port):
    state = target_session.state_path()
    directory = os.path.dirname(state) or "."
    return os.path.join(directory, f"daemon-{host}-{port}.sock")


def endpoint(path):
    """读描述文件判断传输方式。

    unix socket 文件读不出内容（不是普通文件）；TCP 模式下 daemon 会在同一路径
    写 {transport,host,port,pid,token}。返回 ("unix", None) 或 ("tcp", info)。
    """
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read(512)
    except OSError:
        return "unix", None
    if not text.lstrip().startswith("{"):
        return "unix", None
    try:
        info = json.loads(text)
    except json.JSONDecodeError:
        return "unix", None
    if info.get("transport") == "tcp" and info.get("port"):
        return "tcp", info
    return "unix", None


def _connect(path, timeout=30.0):
    transport, info = endpoint(path)
    if transport == "tcp":
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            sock.connect((info.get("host", "127.0.0.1"), int(info["port"])))
        except OSError:
            sock.close()
            return None
        return sock
    if not hasattr(socket, "AF_UNIX"):
        # Windows：没有 unix socket 时必须由 daemon 走 TCP 回退，这里说明清楚
        raise DaemonError("当前平台不支持 Unix domain socket，等待 daemon 以 TCP 模式启动")
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect(path)
    except OSError:
        sock.close()
        return None
    return sock


def _spawn(host, port, path, evidence):
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    log_path = f"{path}.log"
    idle = os.environ.get("SCREENPILOT_IDLE", "600")
    with open(log_path, "ab", buffering=0) as log:
        subprocess.Popen(
            [
                sys.executable,
                DAEMON,
                "--host", host,
                "--port", str(port),
                "--socket", path,
                "--evidence", evidence,
                "--idle", str(float(idle)),
            ],
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            start_new_session=True,
            close_fds=True,
        )


def _log_tail(path, limit=400):
    """把 daemon 日志最后几行带进错误信息，避免"超时"掩盖 ModuleNotFoundError。"""
    try:
        with open(f"{path}.log", "rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - limit))
            text = fh.read().decode("utf-8", "replace").strip()
    except OSError:
        return "无日志"
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return "log: " + " | ".join(lines[-3:]) if lines else "无日志"


def ensure(host, port, evidence):
    """返回一个已连接的 socket；必要时拉起常驻进程。"""
    path = socket_path(host, port)
    sock = _connect(path)
    if sock is not None:
        return sock

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(f"{path}.lock", "w", encoding="utf-8") as lock:
        try:
            import fcntl

            fcntl.flock(lock, fcntl.LOCK_EX)
        except ImportError:  # 非 posix：退化为无锁
            pass
        sock = _connect(path)
        if sock is not None:
            return sock
        if os.path.exists(path):
            # 进程已死留下的 socket/端口文件：先探活再清，避免撞一次死端口
            _, info = endpoint(path)
            pid = (info or {}).get("pid")
            alive = True
            if isinstance(pid, int):
                try:
                    os.kill(pid, 0)
                except OSError:
                    alive = False
            if not alive:
                try:
                    os.unlink(path)
                except OSError:
                    pass
        _spawn(host, port, path, evidence)
        deadline = time.time() + SPAWN_TIMEOUT
        while time.time() < deadline:
            time.sleep(0.05)
            sock = _connect(path)
            if sock is not None:
                return sock
    raise DaemonError(
        f"常驻进程启动超时（{SPAWN_TIMEOUT}s）：{_log_tail(path)}"
    )


def request(host, port, evidence, cmd, args=None, spawn=True):  # noqa: C901 - 传输分支在此集中
    """发一个请求，返回信封；连接失败抛 DaemonError。

    spawn=False 时绝不拉起常驻进程，连不上就返回 None（供 stop 使用）。
    """
    if spawn:
        sock = ensure(host, port, evidence)
    else:
        sock = _connect(socket_path(host, port))
        if sock is None:
            return None
    transport, info = endpoint(socket_path(host, port))
    message = {"cmd": cmd, "args": args or {}}
    if transport == "tcp" and info and info.get("token"):
        message["auth"] = info["token"]
    try:
        payload = json.dumps(message, ensure_ascii=False)
        sock.sendall(payload.encode() + b"\n")
        buffer = b""
        while not buffer.endswith(b"\n"):
            chunk = sock.recv(1 << 20)
            if not chunk:
                break
            buffer += chunk
    finally:
        sock.close()
    if not buffer.strip():
        raise DaemonError(f"常驻进程无响应：{_log_tail(socket_path(host, port))}")
    return json.loads(buffer.decode())
