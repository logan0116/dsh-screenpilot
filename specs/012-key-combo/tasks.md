# Tasks: 组合键与输入法路径

**Feature**: `012-key-combo` · 需求 `012-AR` · 目标版本 `v0.3.0`

## 实现

- [X] T1 `screen_protocol.parse_combo`：`mod[+mod...]+key` 解析，别名归一，单按修饰键合法。
- [X] T2 `MODIFIER_KEYSYM`：ctrl/control、alt/option、shift、meta/win/super/cmd。
- [X] T3 `RemoteScreen.key_combo`：单连接内 修饰键按下 → 主键按下/抬起 → 逆序抬起。
- [X] T4 `act(kind=key)` 改走 `parse_combo`，非法输入返回 `PROTOCOL_ERROR` 且零副作用。
- [X] T5 工具描述与 README 补组合键语法、`shift` 单按、输入法处置路径。

## 验证

- [X] V1 `python/test_key_combo.py` 11 条全绿（解析 8 条 + 发送 3 条）。
- [X] V2 全量单测 27 条 PASS。
- [X] V3 68 号机：`shift`、`ctrl+space`、`win+space`、`alt+tab` 均 `ok=true`。
- [X] V4 68 号机：`ctrl+不存在的键` → `PROTOCOL_ERROR`，`hint` 列出可用修饰键。

## 未验证（如实记录）

- [ ] 输入法是否真的被切到英文：68 号机是 kiosk 式全屏（应用中心 + 华中数控 HMI），
  没有可安全输入的文本框，`win` 键也不弹开始菜单，无法在不干扰现场的前提下观察候选词。
- [ ] `alt+f4` 关闭前台窗口：会关掉现场正在跑的应用，未在共用台架上执行。
- [ ] 中文/emoji 输入仍不支持（`UNSUPPORTED`，需剪贴板通道）。
