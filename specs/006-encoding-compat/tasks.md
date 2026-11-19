# Tasks: RFB 编码兼容与错误分类

**Feature**: `006-encoding-compat` · 需求 `006-AR` · 目标版本 `v0.2.0`

## 实现

- [X] T1 `remote_screen` 拆出 `UnsupportedEncoding`（带 `encoding` 属性），替代裸 `RuntimeError`。
- [X] T2 `_read_frame` 支持 CopyRect（`enc==1`）：读源坐标，从本帧已绘制区域裁剪粘贴。
- [X] T3 `screen_protocol`：`describe`/`act`（before/after）/`settle` 四处捕获 `UnsupportedEncoding` → `UNSUPPORTED`，`OSError` → `NO_CONNECTION`。

## 验证

- [X] V1 合成帧（Raw 红块 + CopyRect）：`(2,0)==(0,0)==(255,0,0)`，`non_zero=4`，无异常。
- [X] V2 合成帧 `enc=7`：抛 `UnsupportedEncoding`，`encoding=7`，信息含编号。
- [X] V3 协议映射：`describe` 遇 `UnsupportedEncoding` → `ok=false`、`error.code=UNSUPPORTED`。
- [X] V4 真实台架回归：`describe` → `ok=true`，60 条文本（Raw 路径未受影响）。
