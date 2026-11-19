# Tasks: VNC Authentication

**Feature**: `005-vnc-auth` · 需求 `005-AR` · 目标版本 `v0.3.0`

## 实现

- [X] T1 新增 `python/vnc_auth.py`：`des_key`（截断补零 + 逐字节比特反转）、`auth_response`（TripleDES/ECB 等价 DES）、`VncAuthError`/`VncAuthUnavailable`。
- [X] T2 `remote_screen._connect`：识别服务端安全类型，含 1 用 None，含 2 走认证，其余 `UnsupportedAuth`。
- [X] T3 `_authenticate`：写类型 2 → 读 challenge → 回应答 → 读 SecurityResult（失败时读 reason）。
- [X] T4 握手失败关闭 socket（`_connect` 包一层 try/except）。
- [X] T5 协议层把 `VncAuthError` 映射为 `NO_CONNECTION`（describe/act/settle 四处）。
- [X] T6 插件配置 `vncPassword` → 环境变量 `SCREENPILOT_VNC_PASSWORD`；`requirements.txt` 加 `cryptography>=41`；README 补说明。

## 验证

- [X] V1 交叉验证：`auth_response` 与 `openssl enc -des-ecb -provider legacy` 逐字节一致（密码 `s3cret!`，challenge 0x11…0x00）。
- [X] V2 密钥派生：与测试内独立写法（字符串反转）一致；短密码补零、`'a'→0x86`。
- [X] V3 端到端（本地最小 RFB 服务端）：正确密码握手成功并取到 8×8 帧。
- [X] V4 端到端：密码错误 → `NO_CONNECTION` + 「认证失败」；缺密码 → `NO_CONNECTION` + hint 含环境变量名。
- [X] V5 端到端：服务端提供类型 1 时不需要密码，握手正常。
- [X] V6 真机回归：68 号机（无认证）`describe` 正常，199 条文本。
- [X] V7 全量单测 39 条 PASS。

## 未验证（如实记录）

- [ ] 真实带密码的 VNC 服务端（如 TightVNC/x11vnc 开密码）未联调：手头没有这样的台架，
      现有证据是「openssl 交叉验证 + 自建服务端端到端」，不能替代真机。
- [ ] 非 ASCII 密码（VNC 密码通常按拉丁字符处理，当前按 UTF-8 取前 8 字节）。
