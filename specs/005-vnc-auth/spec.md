# Feature Specification: VNC Authentication（安全类型 2）

**Feature Branch**: `005-vnc-auth`

**Created**: 2026-11-19

**Status**: Implemented

**Input**: 需求 005-AR。带密码的 VNC 服务端连不上：`_connect` 遇到安全类型不是 1 就直接抛异常。

## 背景与问题证据

| 问题 | 证据 | 影响 |
|---|---|---|
| 只接受无认证 | 旧实现只挑类型 1，其余抛 `RuntimeError` | 现场开了密码的台架完全连不上 |
| 无法验证 | 手头没有带密码的台架 | 该需求一直被后移 |

## Clarifications

- Q: 没有带密码的台架怎么验？ → A: 两条独立证据链：①DES 结果用 openssl 命令行交叉验证（外部实现）；②本地起最小 RFB 服务端（要求类型 2）端到端跑真实 TCP 握手与取帧。
- Q: DES 自己实现还是用库？ → A: 用 `cryptography` 的 TripleDES（密钥重复三次等价单 DES），不手写分组密码；缺库时明确报错，不静默降级。
- Q: 密码怎么传？ → A: 插件配置 `vncPassword`，经环境变量 `SCREENPILOT_VNC_PASSWORD` 传给 sidecar，不进 argv（`ps` 看不到）。
- Q: 认证失败算什么错误？ → A: `NO_CONNECTION`，message 说明密码错误或服务端拒绝，hint 指向配置项。
- Q: 密码为空但有类型 1 怎么办？ → A: 优先用类型 1（无认证），不需要密码。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 带密码的台架能连上 (Priority: P1)

**Independent Test**: 本地最小 RFB 服务端要求类型 2、密码`s3cret!`；客户端配同一密码 → 握手成功并取到 8×8 画面。

**Acceptance Scenarios**:

1. **Given** 服务端只提供类型 2 与正确密码，**When** 客户端带对密码连接，**Then** `ok=true`、`screen.w/h` 与 ServerInit 一致。
2. **Given** 服务端同时提供类型 1 和 2，**When** 连接，**Then** 选类型 1，不要求密码。
3. **Given** 服务端只提供类型 2、客户端密码错误，**When** 连接，**Then** `ok=false`、`error.code=NO_CONNECTION`、message 含「认证失败」。
4. **Given** 服务端只提供类型 2、客户端没配密码，**When** 连接，**Then** `NO_CONNECTION`，hint 含 `SCREENPILOT_VNC_PASSWORD`。
5. **Given** 服务端提供两者都不支持的类型（如 16），**When** 连接，**Then** `UNSUPPORTED` 并列出类型。

### User Story 2 - DES 质询应答正确 (Priority: P1)

**Independent Test**: `auth_response("s3cret!", 16字节challenge)` 与 `openssl enc -des-ecb -provider legacy` 用同一把（比特反转后的）密钥算出的结果逐字节相同。

**Acceptance Scenarios**:

6. **Given** 任意密码与 challenge，**When** 计算应答，**Then** 输出 16 字节，且与 openssl 独立计算结果一致。
7. **Given** 密码`password`，**When** 派生 DES 密钥，**Then** 密钥 = 各字节比特反转（测试用字符串反转的另一种写法交叉核对）。
8. **Given** 短密码`ab`，**When** 派生密钥，**Then** 补零到 8 字节且首字节为 `0x86`（`'a'=0x61` 反转）。

### User Story 3 - 失败不泄漏套接字 (Priority: P2)

认证失败时连接要关闭，不能把 socket 留成半开。

**Acceptance Scenarios**:

9. **Given** 认证失败，**When** `_connect` 抛错，**Then** 底层 socket 已关闭（单测中无 `ResourceWarning`）。

## Requirements *(mandatory)*

- **FR-001**: 实现 RFB 安全类型 2：读 16 字节 challenge、回 16 字节 DES 应答、读 SecurityResult。
- **FR-002**: 密码来源为环境变量 `SCREENPILOT_VNC_PASSWORD`（插件配置 `vncPassword` 注入）。
- **FR-003**: DES 密钥 = 密码截断/补零到 8 字节后逐字节比特反转。
- **FR-004**: 认证失败/缺密码 → `NO_CONNECTION` 并给出可操作提示；不支持的只有类型时 `UNSUPPORTED`。
- **FR-005**: 握手失败必须关闭 socket。
- **FR-006**: 依赖 `cryptography`，缺库时报 `VncAuthUnavailable`，由协议层转成 `NO_CONNECTION` 并提示安装。

## 非目标

- 客户端证书、TLS 隧道、SSV 等其它安全类型。
- 密码加密存储（当前由 profile 配置或环境变量提供）。

## Success Criteria *(mandatory)*

- **SC-001**: `python -m unittest discover -p "test_*.py"` 39 条全 PASS（含 8 条认证单测 + 4 条端到端）。
- **SC-002**: 真机（无认证的 68 号机）不受影响：`describe` 正常返回 199 条文本。
- **SC-003**: 认证失败、缺密码两种路径均返回 `NO_CONNECTION` 且提示可操作。
