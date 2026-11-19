# Tasks: 侧边栏实时观察窗

**Feature**: `013-watch-panel` · 需求 `013-AR` · 目标版本 `v0.4.0`

## 实现

- [ ] T1 `screen_protocol.frame()`：抓帧 → 降采样 → JPEG → base64，不落证据文件。
- [ ] T2 `daemon` 增加 `frame` 命令（带 scale/quality 参数）。
- [ ] T3 `lib/server.js`：unix socket 桥 + `/api/screenpilot/{state,frame,stream,input}` 路由。
- [ ] T4 `lib/index.js`：`ctx.effect` 里注册路由，卸载时注销。
- [ ] T5 `lib/client.js`：注册 `sidebar.right.pane.tab`，SSE 收帧渲染 `<img>`，状态行 + 点击接管。
- [ ] T6 `package.json`：补 `dsh.client`（platform/inject）与 `./client` 导出。

## 验证

- [ ] V1 `frame` 命令直连 unix socket：返回 base64 JPEG，尺寸为原图 50%。
- [ ] V2 `/api/screenpilot/state` 返回会话目标与 daemon 存活状态。
- [ ] V3 `/api/screenpilot/stream` 连续推帧，断开后服务端停止抓帧。
- [ ] V4 面板出首帧 ≤1 秒，状态行帧号递增。
- [ ] V5 面板点击后远端画面变化（对照 `screen_describe`）。
- [ ] V6 无会话时点击返回 `NOT_STARTED`。
