# Feature Specification: screen_stop 会话释放

**Feature Branch**: `003-stop-session`

**Created**: 2026-11-19

**Status**: Draft

**Input**: 需求 003-AR。README 的工具表里列了 `screen_stop`，实现里没有这个工具；常驻 sidecar 上线后更需要一个显式的关停入口。

## 背景与问题证据

| 问题 | 证据 | 影响 |
|---|---|---|
| 工具表与实际注册不一致 | README 工具表列出 `screen_stop`；`lib/index.js:100-212` 只注册 5 个工具 | 文档承诺的能力不存在 |
| 常驻进程无工具层出口 | `screen_cli.py` 已有内部 `shutdown`，但只能命令行调用 | 会话用完无法释放，占着 VNC 连接与内存 |
| 未启动时语义缺失 | 协议错误码表含 `NOT_STARTED`，实现从未产出 | 调用方无法区分「已释放」与「服务异常」 |

## Clarifications

### Session 2026-11-19

- Q: stop 之后会话文件还要保留吗？ → A: 清除。释放语义包含「忘掉当前目标」，下次调用回落到配置或显式 target。
- Q: 没有会话时 stop 返回什么？ → A: `NOT_STARTED`，且**不得**为此拉起常驻进程（stop 不产生副作用）。
- Q: 重复调用 stop 算幂等吗？ → A: 是：第二次仍是 `NOT_STARTED`，不是错误堆栈，也不会挂起。
- Q: stop 与内部 `shutdown` 是否合并？ → A: 合并为一个命令 `stop`，工具层 `screen_stop` 与命令行共用；`shutdown` 保留为别名。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 用完释放会话 (Priority: P1)

调用 `screen_stop` 后，常驻进程退出、VNC 连接断开、socket 文件被删除，会话文件也被清除。

**Why this priority**: 常驻进程把资源占用从「一次调用」延长到「开机期间」，没有出口就会越积越多。

**Independent Test**: `start` 后记下 `screen.pid`，`stop` 后该 pid 消失、socket 文件不存在、会话文件不存在。

**Acceptance Scenarios**:

1. **Given** 会话已启动，**When** `screen_stop`，**Then** 返回 `ok=true`，`data.stopped=true`，且 `screen.pid` 是有过会话的那个进程。
2. **Given** `screen_stop` 返回后，**When** 检查进程与文件，**Then** 该 pid 不存在、`daemon-<host>-<port>.sock` 不存在。
3. **Given** 会话已启动且会话文件存在，**When** `screen_stop`，**Then** 会话文件被删除；随后的 `describe` 回落到 `defaultTarget`（`screen.source=default`）。

### User Story 2 - 无事可做时明确回答 (Priority: P1)

没有会话时调用 `screen_stop`，得到 `NOT_STARTED` 而不是拉起一个新进程或报内部错误。

**Why this priority**: stop 不该有副作用；否则"关停脚本"反而会让进程活起来。

**Independent Test**: 干净状态下（无 socket、无会话文件）调用 `screen_stop`，返回 `NOT_STARTED`，且调用前后都不存在 socket 文件。

**Acceptance Scenarios**:

4. **Given** 没有任何会话，**When** `screen_stop`，**Then** 返回 `ok=false`、`error.code=NOT_STARTED`。
5. **Given** 刚刚 `screen_stop` 过一次，**When** 再执行一次，**Then** 仍返回 `NOT_STARTED`，且不产生新进程（`/proc` 中无该目标 daemon）。
6. **Given** socket 文件残留但进程已死，**When** `screen_stop`，**Then** 返回 `NOT_STARTED`，并清理残留 socket，不拉起新进程。

## Requirements *(mandatory)*

- **FR-001**: 注册 `screen_stop` 工具，无参数，调用 sidecar 的 `stop` 命令。
- **FR-002**: `stop` 不拉起常驻进程；连接不上时直接返回 `NOT_STARTED`。
- **FR-003**: `stop` 成功后删除 socket 文件与会话文件；daemon 自行退出。
- **FR-004**: `NOT_STARTED` 加入 `screen_protocol.CODES`，与 README 的错误码表对齐。
- **FR-005**: README 工具表与当前状态与实际一致（六个工具全部存在）。

## 非目标

- 多会话管理（一个目标一个进程，切目标即切进程）。
- 会话超时策略调整（`SCREENPILOT_IDLE` 已覆盖）。

## Success Criteria *(mandatory)*

- **SC-001**: `start` → `stop` 后，pid 消失、socket 与会话文件均不存在。
- **SC-002**: 干净状态下 `stop` 返回 `NOT_STARTED`，且不产生新进程、不留 socket。
- **SC-003**: README 工具表的六个工具与 `lib/index.js` 注册的工具一一对应。
