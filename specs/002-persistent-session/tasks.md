# Tasks: 会话常驻与跨调用帧缓存

**Feature**: `002-persistent-session` · 需求 `002-AR` · 目标版本 `v0.2.0`

## 实现

- [X] T1 新增 `python/daemon.py`：每目标一个进程，Unix socket 收换行分隔 JSON，进程内只持有一个 `ScreenProtocol`，因此 `_last`/`_prev`/`seq` 跨请求存活；空闲超时退出并清理 socket。
- [X] T2 新增 `python/client.py`：按需拉起（`flock` 串行化，避免并发冷启动起两个进程）、残留 socket 清理、请求/回执。
- [X] T3 `python/screen_cli.py` 改为纯客户端：参数与目标解析沿用 001，新增内部命令 `shutdown`/`ping`；`start` 走 `settle` 后写会话文件。
- [X] T4 信封 `screen` 增加 `pid` 与 `cost`（本次请求耗时 ms）；`source` 由 CLI 按解析结果覆盖，daemon 侧只作兜底。
- [X] T5 `.gitignore` 增加 `.tmp-*/`、`.tmp-*.json`，避免测试产物入库。

## 验证（台架 192.168.1.68:5900，1080×1920）

- [X] V1 `verify --kind changed` 跨调用可用：`ok=true`、`data.diff=0`，不再报「没有可比的前一帧」。
- [X] V2 `act` 的 `before` 复用缓存：与上一次 `describe` 证据 `md5sum` 相同（`84ecf5de…`），只是换了文件名落盘。
- [X] V3 `describe` 连续两次 `pid` 相同（同一次 shell 调用内 pid=20/20）。
- [X] V4 `shutdown` 后进程退出、socket 被删；再次调用自动拉起（新 pid=28）。
- [X] V5 `kill -9` 留下残留 socket 时，下次调用能清理并拉起（新 pid=104），返回正常结果。
- [X] V6 并发冷启动两个客户端只起一个进程（两者 pid 相同，socket 文件 1 个）。
- [X] V7 `SCREENPILOT_IDLE=3` 时空闲退出：进程消失、socket 清理。
- [ ] V8 SC-002 耗时目标**未达标**：冷 9438ms → 热 6219/5544ms，降约 41%（要求 ≤一半）。根因是 OCR 全屏分列扫描（3 次裁剪），模型加载只占约 3.4s；OCR 性能不在本需求范围。

## 文档

- [X] T6 README：常驻进程与 socket、`SCREENPILOT_IDLE`、`shutdown`、Windows 暂不支持 Unix socket。

## 已知限制

- 本次验证在沙箱内完成，沙箱每次命令结束会销毁 PID 命名空间，因此**跨 bash 调用的常驻性无法在此环境实测**；同一 shell 内的多个独立 CLI 进程共享同一 daemon（V3/V4/V5 即是该场景），宿主机上 daemon 由 `start_new_session` 脱离父进程，可跨工具调用存活。
- Windows 无 `AF_UNIX` 时返回 `NO_CONNECTION` 并提示（FR-008 的实现选择：CLI 侧 `client.DaemonError` → `NO_CONNECTION`；命名管道留待后续）。
