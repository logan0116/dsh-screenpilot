# Feature Specification: RFB 编码兼容与错误分类

**Feature Branch**: `006-encoding-compat`

**Created**: 2026-11-19

**Status**: Draft

**Input**: 需求 006-AR。客户端只认 Raw（`enc==0`），遇到 CopyRect 或 Tight/ZRLE 等编码直接 `RuntimeError`，异常穿透协议层，调用方拿到的是「常驻进程无响应」而不是可判断的错误码。

## 背景与问题证据

| 问题 | 证据 | 影响 |
|---|---|---|
| 只支持 Raw | `remote_screen.py` 旧实现 `if enc != 0: raise RuntimeError(...)` | 服务端一旦发 CopyRect/Tight 就崩 |
| 异常穿透 | 旧实现抛裸 `RuntimeError`，`screen_protocol` 只捕 `OSError` | 常驻进程回执丢失 → 客户端报 `NO_CONNECTION`，掩盖真实原因 |
| 编码不可见 | 错误信息只给「unsupported encoding」不含编号 | 无法判断该在服务端关哪个编码 |

## Clarifications

### Session 2026-11-19

- Q: 哪些编码必须支持？ → A: Raw（0）与 CopyRect（1）。其余返回 `UNSUPPORTED` 并指名编码号。
- Q: CopyRect 的源从哪取？ → A: 本帧已绘制区域（当前客户端每次请求全帧非增量，CopyRect 属于防御性支持）。
- Q: 错误码怎么归类？ → A: `UnsupportedEncoding` → `UNSUPPORTED`；网络错误仍是 `NO_CONNECTION`。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - CopyRect 不再崩 (Priority: P1)

服务端发 CopyRect 时能正确复制像素，而不是抛异常。

**Independent Test**: 合成一个「Raw 2×2 红块 + CopyRect 复制到 (2,0)」的更新消息，解码后两处像素相同且非零。

**Acceptance Scenarios**:

1. **Given** 一帧含 Raw 矩形与 CopyRect 矩形，**When** 解码，**Then** `(2,0)` 与 `(0,0)` 像素一致，不抛异常。
2. **Given** Raw 矩形数据，**When** 解码，**Then** `non_zero>0`（画面非空判定仍有效）。

### User Story 2 - 未实现编码给出可判断的错误 (Priority: P1)

Tight/ZRLE 等编码返回 `UNSUPPORTED`，错误信息含编码号，协议层不再把它当网络故障。

**Independent Test**: 合成 `enc=7` 的消息 → 抛 `UnsupportedEncoding(7)`；`describe` 将其映射为 `error.code=UNSUPPORTED`。

**Acceptance Scenarios**:

3. **Given** 更新消息里编码号为 7，**When** 解码，**Then** 抛 `UnsupportedEncoding`，`encoding=7`。
4. **Given** 远端只发未实现编码，**When** 调用 `describe`，**Then** 返回 `ok=false`、`error.code=UNSUPPORTED`，`error.hint` 指向在服务端关闭或改回 Raw/CopyRect。
5. **Given** 网络不可达，**When** 调用，**Then** 仍是 `NO_CONNECTION`（不误判为编码问题）。

### User Story 3 - 真实台架回归 (Priority: P2)

真实台架（只发 Raw）不受影响。

**Acceptance Scenarios**:

6. **Given** 台架 192.168.1.68:5900，**When** `describe`，**Then** `ok=true` 且文本条数正常。

## Requirements *(mandatory)*

- **FR-001**: 支持 Raw（0）；支持 CopyRect（1），源矩形取自本帧已绘制区域。
- **FR-002**: 其它编码抛 `UnsupportedEncoding`（带编码号），不抛裸 `RuntimeError`。
- **FR-003**: `screen_protocol` 的 `describe`/`act`/`settle` 把 `UnsupportedEncoding` 映射为 `UNSUPPORTED`，`OSError` 仍映射为 `NO_CONNECTION`。
- **FR-004**: 错误提示写明「在服务端关闭 Tight/ZRLE 或改用 Raw/CopyRect」。

## 非目标

- Tight/ZRLE/Zlib 解码实现（当前台架不发）。
- 增量更新与帧缓冲复用。

## Success Criteria *(mandatory)*

- **SC-001**: 合成帧的 CopyRect 解码结果与源像素一致。
- **SC-002**: `enc=7` → `UNSUPPORTED`，且不再出现 `NO_CONNECTION` 误报。
- **SC-003**: 真实台架 `describe` 正常（60 条文本）。
