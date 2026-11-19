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


def _connect(path, timeout=30.0):
    if not hasattr(socket, "AF_UNIX"):
        raise DaemonError("当前平台不支持 Unix domain socket，常驻会话不可用")
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
        if os.path.exists(path):  # 进程已死留下的 socket 文件
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
    raise DaemonError(f"常驻进程启动超时（{SPAWN_TIMEOUT}s），见 {path}.log")


def request(host, port, evidence, cmd, args=None, spawn=True):
    """发一个请求，返回信封；连接失败抛 DaemonError。

    spawn=False 时绝不拉起常驻进程，连不上就返回 None（供 stop 使用）。
    """
    if spawn:
        sock = ensure(host, port, evidence)
    else:
        sock = _connect(socket_path(host, port))
        if sock is None:
            return None
    try:
        payload = json.dumps({"cmd": cmd, "args": args or {}}, ensure_ascii=False)
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
        raise DaemonError("常驻进程无响应（连接被关闭）")
    return json.loads(buffer.decode())
