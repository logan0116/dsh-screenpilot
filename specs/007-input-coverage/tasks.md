# Tasks: 输入覆盖

**Feature**: `007-input-coverage` · 需求 `007-AR` · 目标版本 `v0.2.0`

## 实现

- [X] T1 `remote_screen`：删除 9 符号映射表，改为「ASCII 直发 + `SHIFTED` 映射（US 布局）」。
- [X] T2 `remote_screen.type_text`：整串先校验，非 ASCII 抛 `UnsupportedChar`，一个键都不发（原子性）。
- [X] T3 `screen_protocol.act`：`type` 前置校验，返回 `UNSUPPORTED` 并给码点与剪贴板提示，避免异常冒泡。
- [X] T4 `screen_protocol.KEYSYM`：补 `f1`–`f12`、home/end/insert/delete/pageup/pagedown/space/ctrl/alt/shift。

## 验证

- [X] V1 keysym 序列（捕获式假连接）：`A!z?1` → `shift+a, shift+1, z, shift+/, 1`；`a b/c:d_e` → `a, space, b, /, c, shift+;, d, shift+-, e`。
- [X] V2 原子性：`café` / `中文` 被拒绝时已发送事件数均为 0。
- [X] V3 真实台架（192.168.1.68:5900）：搜索框聚焦后两次 `type abc123` 再 `type zz9`，OCR 读回 `ABC23ABC23zz9`，末尾 `zz9` 证明字符落屏。
- [X] V4 真实台架 `type 测试中文` → `UNSUPPORTED`，`error.message` 含 `'测' (U+6D4B)`。

## 已知偏差

- V3 中 OCR 把 `abc123` 读成 `ABC23`（字体小、数字与字母易混），故以「追加的 `zz9` 出现在末尾」作为落屏证据，而非逐字符一致。
