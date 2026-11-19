# Feature Specification: 侧边栏实时观察窗

**Feature Branch**: `013-watch-panel`

**Created**: 2026-11-19

**Status**: Implemented

**Input**: 需求 013-AR。用户希望像 ego-browser 的观察窗那样，在 DSH 右侧栏直接看到远端屏幕正在发生什么，而不必翻看 `capture=xxx.png` 证据文件。

## 背景与问题证据

| 问题 | 证据 | 影响 |
|---|---|---|
| 只能看证据文件名 | 工具渲染只回 `capture=1795…png` | 想知道远端在干什么要自己去开图片 |
| 无法手动接管 | 只有模型能调 `screen_act` | 人想点一下得另开 VNC 客户端 |
| ego-browser 有先例 | `lib/client.js:2229` 注册 `sidebarRightTabs`；`lib/index.js:4249` 用 `webServer.register` 挂同源路由 | 路径已验证，照做即可 |

## Clarifications

- Q: 走哪条通道？ → A: host 侧 `webServer.register({kind:"prefix", path:"/api/screenpilot"})` 挂同源路由；client 侧注册 `sidebar.right.pane.tab`。不新开端口、不跨域。
- Q: 帧从哪来？ → A: Node 直接连 sidecar 的 unix socket 发 `frame` 命令，不经过 Python CLI（省每次约 5 秒启动）。
- Q: 帧率？ → A: 受 RFB 全帧抓取限制约 0.6fps，本需求明确不承诺流畅；增量更新另立需求。
- Q: 每帧要不要存证据？ → A: 不存。观察窗每帧写 PNG 会写爆 evidence 目录，只在 `describe/act` 等动作时留证。
- Q: 手动接管的范围？ → A: 点击（坐标）与滚动；不做键盘输入（输入法问题未解，见 012）。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 在侧栏看到远端画面 (Priority: P1)

右侧栏出现 `screenpilot` 面板，自动播放远端当前画面，并显示目标与帧信息。

**Acceptance Scenarios**:

1. **Given** 会话已建立，**When** 打开观察窗，**Then** 面板显示远端画面并在 1 秒内出现第一帧。
2. **Given** 面板在播放，**When** 远端画面变化，**Then** 面板在约 2 个抓帧周期内更新（约 0.6fps）。
3. **Given** 没有会话（无 daemon），**When** 打开观察窗，**Then** 面板显示「未连接，先调用 screen_start」，不反复报错。

### User Story 2 - 面板自证状态 (Priority: P1)

面板顶部显示当前 `host:port`、帧序号与最近更新时间，便于判断看到的是不是活画面。

**Acceptance Scenarios**:

4. **Given** 有会话，**When** 读取 `/api/screenpilot/state`，**Then** 返回 `{session:{host,port},daemon:{alive}}`。
5. **Given** 帧流运行中，**When** 观察面板，**Then** 能看到帧计数与时间戳增长。

### User Story 3 - 手动接管 (Priority: P2)

在面板上点击，等价于 `screen_act(click, xy)`，直接作用到远端。

**Acceptance Scenarios**:

6. **Given** 面板显示画面，**When** 点击画面某点，**Then** `POST /api/screenpilot/input` 把该点映射回原图坐标并让 daemon 执行 click。
7. **Given** 点击成功，**When** 观察下一次刷新，**Then** 画面出现动作后的变化（或明确无变化）。
8. **Given** 没有会话，**When** 点击，**Then** 返回 `NOT_STARTED`，不改远端状态。

## Requirements *(mandatory)*

- **FR-001**: host 侧注册 `/api/screenpilot` 前缀路由，提供 `state`/`frame`/`stream`/`input`。
- **FR-002**: `stream` 用 SSE（`text/event-stream`），每帧 `data: {"jpeg":"<base64>","seq":n,"ts":ms}`；客户端断开即停。
- **FR-003**: 帧由 sidecar 的 `frame` 命令产出（降采样 0.5、JPEG q60），不写证据文件。
- **FR-004**: Node 通过 unix socket 直连 sidecar，socket 路径沿用 `SCREENPILOT_STATE` 同目录规则。
- **FR-005**: client 侧注册 `sidebar.right.pane.tab`，展示画面 + 状态行；无会话时给出可操作提示。
- **FR-006**: `input` 只支持 click 与 scroll，坐标按降采样比例换算回原图；无会话返回 `NOT_STARTED`。
- **FR-007**: 面板卸载时关闭 SSE、清理定时器。

## 非目标

- RFB 增量更新与流畅帧率（另立需求）。
- 面板内键盘输入、文件下载、多目标并排。
- 录制/回放。

## Success Criteria *(mandatory)*

- **SC-001**: 侧栏出现 `screenpilot` 面板，1 秒内出首帧，状态行显示 `host:port` 与帧号。
- **SC-002**: 面板点击能真实作用到远端（用一次 `screen_describe` 前后对比确认）。
- **SC-003**: 无会话时面板给提示、点击返回 `NOT_STARTED`，不产生副作用。
