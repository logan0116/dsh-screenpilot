# Tasks: 剪贴板输入

**Feature**: `018-clipboard-paste` · 需求 `018-AR` · 目标版本 `v0.5.0`

- [X] T1 `RemoteScreen.set_clipboard()`：ClientCutText(6) + 长度 + UTF-8。
- [X] T2 `act(type)` 按 `input_mode` 分流（auto/keysym/clipboard）。
- [X] T3 `data.input_mode` 报通道；未知取值 PROTOCOL_ERROR。
- [X] T4 透传 daemon → CLI → 工具层。
- [X] V1 单测 6 条全绿。
- [ ] V2 真机粘贴中文（有意留待同事在安全工件上验）。
