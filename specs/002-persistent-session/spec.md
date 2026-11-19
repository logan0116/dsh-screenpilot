# Feature Specification: 会话常驻与跨调用帧缓存

**Feature Branch**: `002-persistent-session`

**Created**: 2026-11-19

**Status**: Draft

**Input**: 需求 002-AR。每次工具调用都新起一个 python 进程，`_last/_prev` 随进程消失，`verify(changed)` 永远报「没有可比的前一帧」，OCR 模型每次重新加载。

## 背景与问题证据

| 问题 | 证据 | 影响 |
|---|---|---|
| 状态随进程消失 | `screen_cli.py` 每次 `ScreenProtocol(RemoteScreen(), TextLocator(), ...)` 新建实例，`_last/_prev` 为实例属性（`screen_protocol.py:43-44`） | 跨调用的「上一帧」不存在 |
| `changed` 断言必然失败 | `screen_protocol.py:171-174` 无前帧即 `PROTOCOL_ERROR` | 断言能力的一半用不了 |
| `act` 的前帧不真实 | `screen_protocol.py:88-94` 无缓存时现抓一帧当「动作前」 | 前后对比可能同帧，证据不成立 |
| 每次重载 OCR | `ocr_locator.py` 首次扫描构造 RapidOCR（模型约 2s） | 每次调用 5–8s，交互不可用 |

## Clarifications

### Session 2026-11-19

- Q: 常驻的粒度是什么？ → A: 每个目标（host:port）一个进程；socket 路径由目标决定，切目标即切进程。
- Q: 谁负责拉起？ → A: 客户端首个请求时按需拉起（懒启动），并加文件锁避免并发重复拉起。
- Q: 空闲要不要退出？ → A: 要，默认 600s 无请求退出；下次调用自动重新拉起。
- Q: 进程崩了怎么办？ → A: 客户端连不上就重新拉起一次；拉起后仍连不上则返回 `NO_CONNECTION`，不静默卡死。
- Q: 要不要现在就做 `screen_stop`？ → A: 常驻进程需要一个关停入口，本需求先提供内部 `shutdown` 命令；工具层的 `screen_stop` 与「未启动返回 NOT_STARTED」留到 003。
- Q: 跨平台怎么处理？ → A: 先只支持 Unix domain socket（Linux/macOS）；Windows 的命名管道留待后续，README 写明限制。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 跨调用保持帧信息 (Priority: P1)

连续调用共享同一进程的最近两帧，`verify(changed)` 能比较真实前后帧，`act` 的 `before` 是上次调用留下的帧。

**Why this priority**: 这是 002 的核心；没有它，断言与证据链都只有半条命。

**Independent Test**: 同一目标连续 `describe` → `verify --kind changed`，第二次返回 `changed=true`（画面在动）或稳定的 `diff` 数值，而不是 `PROTOCOL_ERROR`。

**Acceptance Scenarios**:

1. **Given** 已对目标执行一次 `describe`，**When** 再执行 `verify --kind changed`，**Then** 返回 `ok=true` 且 `data.diff` 为整数，不再报「没有可比的前一帧」。
2. **Given** 两次请求之间画面发生明显变化，**When** 执行 `verify --kind changed`，**Then** `data.changed=true`。
3. **Given** 刚执行过 `describe`，**When** 执行 `act --kind click`，**Then** 返回的 `data.before` 与上一次 `describe` 的证据字节一致（复用缓存、不重新抓帧），仅以新文件名落盘。
4. **Given** 全新进程（无任何历史请求），**When** 直接 `verify --kind changed`，**Then** 返回 `ok=false`、`error.code=PROTOCOL_ERROR`，语义与从前一致。

### User Story 2 - 一次加载、快速响应 (Priority: P1)

同一目标的第二次及以后调用不再付 OCR 模型加载成本。

**Why this priority**: 交互可用性取决于每次调用耗时；模型重载占了其中大半。

**Independent Test**: 连续两次 `describe`，第二次墙钟耗时明显低于第一次（目标：≤ 首次的一半）。

**Acceptance Scenarios**:

5. **Given** 冷启动，**When** 第一次 `describe`，**Then** 实际耗时包含模型加载（记录到 `data.cost`）。
6. **Given** 同一目标已热，**When** 再次 `describe`，**Then** 耗时不含模型加载，且 `screen.pid` 与上一次相同。

### User Story 3 - 进程可被发现、可被回收 (Priority: P2)

客户端能判断常驻进程是否活着、能主动关停；空闲进程不会永久占用资源。

**Why this priority**: 没有观测与回收手段，常驻进程会变成"看不见的孤儿"。

**Independent Test**: 连续两次调用输出的 `screen.pid` 相同；执行 `shutdown` 后该 pid 消失、socket 文件被清理。

**Acceptance Scenarios**:

7. **Given** 常驻进程已启动，**When** 任意命令，**Then** 信封 `screen` 里带 `pid`，两次调用 `pid` 相同。
8. **Given** 常驻进程在运行，**When** 执行 `shutdown`，**Then** 进程退出、socket 文件被删除，后续调用要么重新拉起要么报 `NO_CONNECTION`。
9. **Given** socket 文件残留但进程已死，**When** 执行任意命令，**Then** 客户端清理残留并重新拉起，返回正常结果。
10. **Given** 并发两个客户端同时冷启动同一目标，**When** 二者先后请求，**Then** 只存在一个常驻进程（后到者复用先到的 socket）。

## Requirements *(mandatory)*

- **FR-001**: 提供一个常驻进程（每个目标一个），通过 Unix domain socket 接收换行分隔的 JSON 请求，返回与 CLI 一致的信封。
- **FR-002**: 客户端按需拉起常驻进程；用文件锁串行化拉起，避免并发重复启动；拉起失败或超时返回 `NO_CONNECTION`。
- **FR-003**: 常驻进程持有 `RemoteScreen`、`TextLocator`、`ScreenProtocol` 实例，跨请求保留 `_last`/`_prev` 与 `seq`。
- **FR-004**: 空闲超过 `SCREENPILOT_IDLE`（默认 600 秒）退出并清理 socket。
- **FR-005**: 信封 `screen` 增加 `pid` 与 `cost`（本次请求实际耗时，毫秒）。
- **FR-006**: 提供 `shutdown` 命令：回执后退出进程、删除 socket。
- **FR-007**: 输出 JSON 结构、错误码与命令行参数保持与 001 兼容；`screen_*` 工具无需改动调用方式。
- **FR-008**: Windows 上不支持 Unix socket 时，明确返回 `UNSUPPORTED` 并说明，不回退到静默失败。

## 非目标

- 工具层 `screen_stop`（003）。
- 多目标并发会话（一个进程只服务一个目标；切目标即切进程）。
- 帧缓存落盘、进程守护（崩溃自动重启由客户端下次调用触发）。

## Success Criteria *(mandatory)*

- **SC-001**: `verify --kind changed` 在两次调用之间可用，返回 `diff` 数值而非错误。
- **SC-002**: 同一目标连续两次 `describe` 的 `screen.pid` 相同，第二次耗时明显低于首次。**实测（2026-11-19，台架 192.168.1.68:5900，1080×1920）：冷 9438ms → 热 6219/5544ms，降约 41%，未达「≤一半」**；差额主要是 OCR 全屏分列扫描（3 次裁剪识别），模型加载只占约 3.4s。OCR 性能另立需求，本需求只保证「模型只加载一次」。
- **SC-003**: `shutdown` 后进程消失且 socket 被删除；残留 socket 不导致调用失败。
