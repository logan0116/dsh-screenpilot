# Feature Specification: 按键解析健壮性（别名归一 + 未知键拒绝 + daemon 不致命）

**Feature Branch**: `009-keysym-robustness`

**Created**: 2026-11-19

**Status**: Implemented

**Input**: 需求 009-AR。实测 `screen_act(kind=key, value="escape")` 触发 `KeyError: 'escape'`，异常冒泡到 `daemon.serve()`，常驻进程直接退出，后续所有调用返回 `NO_CONNECTION`。

## 背景与问题证据

| 问题 | 证据 | 影响 |
|---|---|---|
| 别名缺失 | `KEYSYM` 只有 `esc`，传 `escape` 直接 `KeyError` | 调用方按常见键名传参即失败 |
| 未命中即抛异常 | `self.remote.tap(KEYSYM[(text or "").lower()])` 无兜底 | 拼错键名等于崩溃 |
| 异常终止常驻进程 | `handle()` 无 try/except，异常冒泡到 `serve()` | 一次坏参数让会话瘫痪，后续调用全部 `NO_CONNECTION`（2026-11-19 实测） |

## Clarifications

- Q: 未知键名怎么处理？ → A: 返回 `PROTOCOL_ERROR` 并附可用按键清单，绝不静默降级。
- Q: 要不要支持组合键（`ctrl+a`）？ → A: 本需求不做，明确拒绝；组合键另立需求。
- Q: 单字符是否当键？ → A: 是，单个可打印 ASCII 字符按其码位作 keysym（`key=a` 等价输入 `a`）。

## User Scenarios & Testing

### User Story 1 - 常见键名别名可用 (Priority: P1)

`key` 接受 `escape`/`page_up`/`pgdn`/`return`/`arrowup` 等常见写法，解析到与规范名相同的 keysym。

**Acceptance Scenarios**:

1. **Given** `key=escape`，**When** 执行，**Then** 发送 keysym `0xFF1B`（与 `esc` 相同）。
2. **Given** `key=page_up` / `page-up` / `pgup`，**When** 执行，**Then** 均发送 `0xFF55`。
3. **Given** `key=A`，**When** 执行，**Then** 发送 `0x61`（小写归一）。

### User Story 2 - 未知键名拒绝且不发送 (Priority: P1)

**Acceptance Scenarios**:

4. **Given** `key=hyper`，**When** 执行，**Then** `ok=false`、`error.code=PROTOCOL_ERROR`，`error.hint` 列出可用按键，假连接 tap 次数为 0。

### User Story 3 - 单请求异常不终止常驻进程 (Priority: P0)

**Acceptance Scenarios**:

5. **Given** `ScreenProtocol` 内部抛任意异常，**When** `handle()` 处理请求，**Then** 返回 `PROTOCOL_ERROR` 信封且进程存活。

## Requirements

- **FR-001**: 按键名先做 `strip().lower()` 归一，再经别名表映射到 `KEYSYM` 规范名。
- **FR-002**: 别名表覆盖 esc/enter/pageup/pagedown/delete/insert/space/方向键的常见写法。
- **FR-003**: 单个可打印 ASCII 字符（`0x20`–`0x7E`）按其码位解析。
- **FR-004**: 未识别按键返回 `PROTOCOL_ERROR`，`error.hint` 含可用按键清单，发送前返回（零副作用）。
- **FR-005**: `daemon.handle()` 捕获所有异常，转 `PROTOCOL_ERROR` 信封并打印 traceback 到 stderr，进程不退出。

## 非目标

- 组合键（`ctrl+a` / `shift+tab`）。
- 非 US 布局与非 ASCII 键名。

## Success Criteria

- **SC-001**: `python -m unittest test_key_robustness` 全绿（10 项）。
- **SC-002**: 真实台架上 `key escape` 返回 `ok=true`，且后续调用不再 `NO_CONNECTION`。
