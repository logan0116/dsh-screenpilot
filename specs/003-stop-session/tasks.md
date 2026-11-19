# Tasks: screen_stop 会话释放

**Feature**: `003-stop-session` · 需求 `003-AR` · 目标版本 `v0.2.0`

## 实现

- [X] T1 `lib/index.js` 注册 `screen_stop`，无参数，调用 CLI `stop`。
- [X] T2 `python/client.py`：`request(..., spawn=False)` —— `stop` 路径绝不拉起常驻进程。
- [X] T3 `python/screen_cli.py`：`stop` 命令（`shutdown` 作别名）；连不上返回 `NOT_STARTED` 并清理残留 socket；成功时清除会话文件。
- [X] T4 `python/session.py`：新增 `clear_session()`。
- [X] T5 `python/screen_protocol.py`：`CODES` 增加 `NOT_STARTED`，与 README 错误码表对齐。
- [X] T6 `python/daemon.py`：`stop`/`shutdown` 同义，回执 `data.stopped=true` 后退出。

## 验证（台架 192.168.1.68:5900）

- [X] V1 干净状态 `stop` → `NOT_STARTED`，且未创建 socket（无副作用）。
- [X] V2 `start` 后 `stop` → `ok=true`、`data.stopped=true`、`screen.pid` 为会话进程；该 pid 退出、socket 与会话文件均不存在。
- [X] V3 再次 `stop` → 仍 `NOT_STARTED`（幂等），不产生新进程。
- [X] V4 残留 socket（进程已死）时 `stop` → `NOT_STARTED`，残留 socket 被清理，未拉起进程。
- [X] V5 `stop` 后 `describe --default …` → `screen.source=default`，功能正常。

## 文档

- [X] T7 README：工具表去掉「（预留）」，补 `NOT_STARTED` 语义与当前状态。
