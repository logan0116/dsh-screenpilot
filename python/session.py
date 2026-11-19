"""目标解析与会话状态：把 target 从参数变成 (host, port)。

解析优先级：显式 target > 会话文件（最近一次 start）> 调用方兜底 > 内置缺省。
会话文件只存 host/port，跨进程最小状态；常驻进程与帧缓存不在本模块。
"""
import json
import os
import re
import time

DEFAULT_HOST = "192.168.1.68"
DEFAULT_PORT = 5900
SUPPORTED_SCHEMES = ("vnc",)

_TARGET_RE = re.compile(r"^([A-Za-z][A-Za-z0-9+.\-]*)://([^/:?#\s]+)(?::(\d{1,5}))?$")


class TargetError(ValueError):
    """target 本身不合法（配置写错）。"""


class UnsupportedTarget(ValueError):
    """target 的 scheme 尚未实现（能力缺口）。"""


def state_path():
    """会话文件位置：SCREENPILOT_STATE 优先，否则 ~/.cache/screenpilot/session.json。"""
    override = os.environ.get("SCREENPILOT_STATE")
    if override:
        return override
    cache = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    return os.path.join(cache, "screenpilot", "session.json")


def parse_target(text):
    """把 vnc://host[:port] 解析成 (scheme, host, port)，非法抛 TargetError。"""
    value = (text or "").strip()
    if not value:
        raise TargetError("target 为空，需要形如 vnc://host[:port]")
    match = _TARGET_RE.match(value)
    if not match:
        raise TargetError(f"target 必须形如 vnc://host[:port]，收到 {value!r}")
    scheme = match.group(1).lower()
    host = match.group(2)
    port = int(match.group(3)) if match.group(3) else DEFAULT_PORT
    if not 1 <= port <= 65535:
        raise TargetError(f"端口必须在 1-65535，收到 {port}")
    return scheme, host, port


def load_session():
    """读会话文件，返回 (host, port)；缺失或损坏返回 None。"""
    try:
        with open(state_path(), encoding="utf-8") as fh:
            data = json.load(fh)
        host = str(data["host"])
        port = int(data["port"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not host or not 1 <= port <= 65535:
        return None
    return host, port


def save_session(host, port):
    """原子写会话文件；成功才调用。"""
    path = state_path()
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"host": host, "port": port, "updated": int(time.time())}, fh)
    os.replace(tmp, path)
    return path


def clear_session():
    """删除会话文件；不存在也算成功。"""
    try:
        os.unlink(state_path())
        return True
    except FileNotFoundError:
        return False


def resolve(explicit=None, fallback=None):
    """按四级优先级解析目标，返回 (host, port, source)。"""
    if explicit:
        scheme, host, port = parse_target(explicit)
        if scheme not in SUPPORTED_SCHEMES:
            raise UnsupportedTarget(f"后端 {scheme}:// 尚未接入，当前只支持 vnc://")
        return host, port, "target"

    saved = load_session()
    if saved:
        return saved[0], saved[1], "session"

    if fallback:
        scheme, host, port = parse_target(fallback)
        if scheme not in SUPPORTED_SCHEMES:
            raise UnsupportedTarget(f"后端 {scheme}:// 尚未接入，当前只支持 vnc://")
        return host, port, "default"

    return DEFAULT_HOST, DEFAULT_PORT, "builtin"
