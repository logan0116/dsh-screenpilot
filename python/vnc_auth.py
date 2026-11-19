"""VNC Authentication（RFB 安全类型 2）。

协议：服务端发 16 字节 challenge，客户端把密码按 DES 加密后回 16 字节。
细节：密码截断/补零到 8 字节，再逐字节反转比特序（VNC 的历史约定），
经 DES-ECB 加密 challenge（16 字节 = 2 个分组）。

DES 用 cryptography 的 TripleDES（密钥重复三次等价于单 DES），
不自己实现分组密码；缺失依赖时明确报错，不静默降级。
"""
from __future__ import annotations

PASSWORD_ENV = "SCREENPILOT_VNC_PASSWORD"


class VncAuthError(RuntimeError):
    """认证失败或缺少密码。协议层把它映射为 NO_CONNECTION。"""


class VncAuthUnavailable(RuntimeError):
    """运行环境缺少 cryptography，无法做 VNC 认证。"""


def _triple_des(password_key: bytes):
    try:
        from cryptography.hazmat.decrepit.ciphers.algorithms import TripleDES
    except ImportError:  # cryptography < 43：旧路径
        from cryptography.hazmat.primitives.ciphers.algorithms import TripleDES

    return TripleDES(password_key * 3)


def des_key(password: str | bytes) -> bytes:
    """VNC 的 DES 密钥：截断/补零到 8 字节，再逐字节反转比特序。"""
    raw = password.encode("utf-8") if isinstance(password, str) else password
    padded = raw[:8].ljust(8, b"\x00")
    return bytes(int(format(byte, "08b")[::-1], 2) for byte in padded)


def auth_response(password: str | bytes, challenge: bytes) -> bytes:
    """按 VNC 约定加密 16 字节 challenge。"""
    if len(challenge) != 16:
        raise VncAuthError(f"challenge 必须是 16 字节，收到 {len(challenge)}")
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, modes
    except ImportError as exc:
        raise VncAuthUnavailable(
            "VNC 认证需要 cryptography：pip install cryptography"
        ) from exc
    encryptor = Cipher(_triple_des(des_key(password)), modes.ECB()).encryptor()
    return encryptor.update(challenge) + encryptor.finalize()
