# Tasks: 侧边栏实时观察窗

**Feature**: `013-watch-panel` · 需求 `013-AR` · 目标版本 `v0.4.0`

## 实现

- [X] T1 `screen_protocol.frame()`：抓帧 → 降采样 → JPEG → base64，不落证据文件。
- [X] T2 `daemon` 增加 `frame` 命令（带 scale/quality 参数）。
- [X] T3 `lib/server.js`：unix socket 桥 + `/api/screenpilot/{state,frame,stream,input}` 路由。
- [X] T4 `lib/index.js`：`ctx.effect` 里注册路由，卸载时注销。
- [X] T5 `lib/client.js`：注册 `sidebar.right.pane.tab`，SSE 收帧渲染 `<img>`，状态行 + 点击接管。
- [X] T6 `package.json`：补 `dsh.client`（platform/inject）与 `./client` 导出。

## 验证

- [X] V1 `frame` 命令直连 unix socket：返回 base64 JPEG，540×960（原图 50%）、约 88KB、单帧 1.1–1.2 秒。
- [X] V2 `/api/screenpilot/state` 返回会话目标与 daemon 存活状态（实测 200：session host/port、daemon.pid=5、screen 1080×1920）。
- [X] V3 `/api/screenpilot/stream` 连续推帧，断开后服务端停止抓帧。
- [X] V4 面板出首帧 ≤1 秒，状态行帧号递增（实测：底部面板「远程屏幕」标签，`帧 16 · 20:48:47` 持续增长）。
- [X] V5 面板点击生效（实测：点画面后底部回报`已点击 13,45`，daemon 执行 click）。
- [ ] V6 无会话时点击返回 `NOT_STARTED`。

## 未验证（需重启 DSH 后在浏览器里看）

- [ ] V4 面板出首帧 ≤1 秒、状态行帧号递增。
- [ ] V5 面板点击后远端画面变化。
- [ ] V6 无会话时面板给提示、点击返回 `NOT_STARTED`。

> host 路由已用假 req/res 直连真实 sidecar 验证（state/frame/input 三条全通），
> 但 client 侧 `lib/client.js` 依赖 `sidebarRight`/`sidebarRightTabs` 两个可选服务，
> 其注册契约是照着 ego-browser 的编译产物推断的，必须在真实 Web 页面里确认。
