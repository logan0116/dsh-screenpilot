# Feature Specification: 远程目标真正生效（target 分发）

**Feature Branch**: `001-target-dispatch`

**Created**: 2026-11-19

**Status**: Draft

**Input**: 需求 001-AR。工具声明了 `target` 参数，实现里却没把它传给 sidecar，只能连硬编码的 `192.168.1.68:5900`。

## 背景与问题证据

| 问题 | 证据 | 影响 |
|---|---|---|
| `target` 被丢弃 | `lib/index.js:110-124` 取到 `args.target` 后只调用 `settle --timeout 8`，未把目标传给 sidecar | 传任何 target 都连同一台机器，多测试台无法使用 |
| 主机硬编码 | `python/remote_screen.py:30` `__init__(host="192.168.1.68", port=5900)` | 换台架必须改代码 |
| 无跨调用状态 | `screen_cli.py:42` 每次新建 `RemoteScreen()`，进程退出即丢 | `screen_start` 的目标无法被后续 `screen_describe` 继承 |
| 非法输入无分类 | 缺 scheme、端口越界、`web://` 都落到同一条失败路径 | 排查时无法区分"配置错"与"连不上" |

## Clarifications

### Session 2026-11-19

- Q: 目标解析的优先级是什么？ → A: 显式 `--target` > 会话文件（最近一次 `screen_start`）> 配置 `defaultTarget` > 内置缺省。
- Q: 跨进程怎么记住目标？ → A: 落一个最小会话文件（`SCREENPILOT_STATE`，默认 `~/.cache/screenpilot/session.json`），只存 host/port；常驻进程留到 002。
- Q: `web://` 这一版要不要支持？ → A: 不支持，返回 `UNSUPPORTED` 并说明；接线属另一条需求。
- Q: 缺 scheme 的 `192.168.1.68:5900` 算不算合法？ → A: 不合法，返回 `PROTOCOL_ERROR`，不发起连接。
- Q: 会话文件损坏怎么办？ → A: 忽略并回退下一级来源，不阻断调用；输出里的 `screen.source` 会显示实际用的是哪一级。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 显式 target 连到指定台架 (Priority: P1)

调用方给 `screen_start` 一个 `vnc://host:port`，会话就建立在该主机上，返回该主机的分辨率与能力清单。

**Why this priority**: 其余四条需求（会话常驻、断言、认证、编码）都以"连对目标"为前提；连错台架时它们全部失效。

**Independent Test**: `python3 python/screen_cli.py start --target vnc://192.168.1.68:5900` 返回 `ok=true` 且 `screen.host=192.168.1.68`。

**Acceptance Scenarios**:

1. **Given** 台架 `vnc://192.168.1.68:5900` 在线，**When** `screen_start` 带该 target，**Then** 返回 `ok=true`，`screen` 含 `host`/`port`/`w`/`h`，`capabilities` 非空。
2. **Given** 未传 target，**When** `screen_start`，**Then** 使用配置的 `defaultTarget`，且 `screen.source=default`。
3. **Given** 目标 `vnc://192.168.1.99:5900` 无服务，**When** `screen_start`，**Then** 返回 `ok=false`、`error.code=NO_CONNECTION`，不写会话文件。
4. **Given** target 缺 scheme（`192.168.1.68:5900`），**When** `screen_start`，**Then** 返回 `error.code=PROTOCOL_ERROR`，且不发起任何连接。
5. **Given** target 的端口为 `70000` 或 host 为空，**When** `screen_start`，**Then** 返回 `error.code=PROTOCOL_ERROR`。
6. **Given** target 为 `web://192.168.1.155:8088`，**When** `screen_start`，**Then** 返回 `error.code=UNSUPPORTED`，`error.hint` 说明 web 后端未接入。

### User Story 2 - 目标跨调用生效 (Priority: P1)

`screen_start` 指定的目标被后续 `screen_describe`/`screen_act`/`screen_verify`/`screen_settle` 沿用，不需要每次重复传 target。

**Why this priority**: 工具是逐次进程调用，目标记不住就等于没生效——这条是 001 真正落地的地方。

**Independent Test**: 先 `start --target vnc://192.168.1.68:5900`，再不带参数跑 `describe`，输出 `screen.source=session` 且 `source_host=192.168.1.68`。

**Acceptance Scenarios**:

7. **Given** 已 `start` 台架 A，**When** 调用 `screen_describe`（不带 target），**Then** 从 A 抓帧，`screen.host` 等于 A 的主机。
8. **Given** 已 `start` A 后进程退出，**When** 新进程执行 `describe`，**Then** 仍连 A（会话文件生效，`screen.source=session`）。
9. **Given** 先 `start` A 再 `start` B，**When** `describe`，**Then** 连到 B（最近一次生效）。
10. **Given** 会话文件被写坏（非 JSON），**When** `describe`，**Then** 回退到 `defaultTarget` 或内置缺省，返回正常结果，`screen.source` 标明回退后的来源。

### User Story 3 - 失败原因可分辨 (Priority: P2)

同一次失败，能从错误码与 `screen.source` 判断是"配置写错""目标不支持"还是"目标不可达"。

**Why this priority**: 没有这一条，现场把 `PROTOCOL_ERROR` 当网络问题查，会耗掉大量时间。

**Independent Test**: 分别构造缺 scheme、`web://`、不可达三种输入，三次输出的 `error.code` 两两不同。

**Acceptance Scenarios**:

11. **Given** 三种非法输入（缺 scheme / `web://` / 不可达），**When** 依次调用，**Then** 依次得到 `PROTOCOL_ERROR`、`UNSUPPORTED`、`NO_CONNECTION`。

## Requirements *(mandatory)*

- **FR-001**: `screen_start` 必须把 target 解析为 `(host, port)` 并传给 sidecar；解析规则仅接受 `vnc://host[:port]`，端口缺省 5900。
- **FR-002**: 目标解析优先级为 显式 target > 会话文件 > 配置 `defaultTarget` > 内置缺省；输出必须用 `screen.source`（`target`/`session`/`default`/`builtin`）标明实际来源。
- **FR-003**: `screen_start` 成功才写会话文件；会话文件只含 `host`、`port` 与写入时间。
- **FR-004**: 非法 target（缺 scheme、host 空、端口越界、含多余路径）返回 `PROTOCOL_ERROR` 且不发起连接。
- **FR-005**: 非 `vnc` scheme 返回 `UNSUPPORTED`，`hint` 说明原因。
- **FR-006**: 会话文件不可读或格式非法时忽略，回退下一级来源，不得抛错。
- **FR-007**: 所有 `screen_*` 工具调用都传递配置的 `defaultTarget` 作为兜底，避免 sidecar 内置缺省与插件配置打架。

## 非目标

- 常驻进程与帧缓存（002）。
- `web://` 后端接线。
- VNC 认证（005）与编码兼容（006）。

## Success Criteria *(mandatory)*

- **SC-001**: 在同一台机器上连续 `start A` → `describe` → `start B` → `describe`，两次 `describe` 的 `screen.host` 分别为 A、B。
- **SC-002**: 三类非法输入的 `error.code` 互不相同，且都不产生连接尝试（台架无连接日志增长）。
- **SC-003**: 会话文件损坏时，功能可用（不抛异常），`screen.source` 非 `session`。
