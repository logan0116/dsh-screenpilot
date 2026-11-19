# Tasks: 远程目标真正生效（target 分发）

**Feature**: `001-target-dispatch` · 需求 `001-AR` · 目标版本 `v0.2.0`

## 实现

- [X] T1 新增 `python/session.py`：`parse_target` 校验 `scheme://host[:port]`、`resolve` 实现四级优先级、`load_session`/`save_session` 落最小会话文件（`SCREENPILOT_STATE`）。
- [X] T2 `python/screen_cli.py`：新增 `start` 子命令与 `--target`/`--default`，按解析结果构造 `RemoteScreen(host, port)`；异常分流为 `PROTOCOL_ERROR`/`UNSUPPORTED`/`NO_CONNECTION`。
- [X] T3 `python/screen_protocol.py`：信封 `screen` 带上 `host`/`port`/`source`；`CODES` 增加 `UNSUPPORTED`；`settle` 捕获 `OSError` 归为 `NO_CONNECTION`（原先直接抛栈）。
- [X] T4 `python/ocr_locator.py`：引擎改为惰性加载，`start` 不再为 OCR 付 2 秒启动成本。
- [X] T5 `lib/index.js`：`screen_start` 透传 `--target`，全部工具透传 `--default`；移除 JS 层的 `web://` 拦截，交由 sidecar 统一判定。

## 验证

- [X] T6 `start --target vnc://192.168.1.68:5900` → `ok=true`，`screen.host/port/source=target`。
- [X] T7 不带 target 的 `describe` → `screen.source=session`，`screen.host=192.168.1.68`，`data.texts` 非空。
- [X] T8 `start --target vnc://192.168.1.99:5900` → `NO_CONNECTION`，会话文件未被改写。
- [X] T9 缺 scheme / 端口 70000 / `web://` → 依次 `PROTOCOL_ERROR`、`PROTOCOL_ERROR`、`UNSUPPORTED`。
- [X] T10 会话文件写坏后 `describe` → 正常返回，`screen.source=default`。
- [ ] T11 `protocol_selftest.py` 12 条仍全 PASS（回归）——**未通过 6/12**，原因见下。

## 文档

- [X] T12 README：补目标解析优先级、`SCREENPILOT_STATE`、`start` 首次调用说明。

## 未通过项与结论

T11 结果是 6/12，但**不是本次改动的回归**：

- 通过 P07–P12：证据链、`NOT_FOUND`、多匹配候选、`OUT_OF_BOUNDS`、`NO_CONNECTION`、空白点击——正好覆盖本次改动的错误分流与连接路径。
- 失败 P01–P06 全部依赖台架画面的固定布局：脚本假设「下载」图标在 `y∈[900,1050]`（`protocol_selftest.py:45`），实测今天在 `(63,468)`；`ADDR=(0,470,1080,560)` 也被图标行占用。台架分辨率仍是 1080×1920，但桌面图标布局与用例作者当时不同。
- 结论：用例与台架状态强耦合，不能当回归门禁。改法属于"测试基建"（12 号候选），本需求不动它。
