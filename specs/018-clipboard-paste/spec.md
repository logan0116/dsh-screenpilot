# Feature Specification: 剪贴板通道输入非 ASCII

**Feature Branch**: `018-clipboard-paste`

**Created**: 2026-11-19

**Status**: Draft

**Input**: 需求 018-AR（同事反馈第6条）。`type` 只能发 ASCII（007-AR 明确拒绝非 ASCII），而上位机场景大量中文配置值/备注。

## 背景

RFB 协议有 `ClientCutText`（消息类型 6），可以把文本写到远端剪贴板；之后发 `Ctrl+V` 即可粘贴。这条绕开输入法，不依赖远端键盘布局。

## Requirements（草案）

- **FR-001**: `type` 遇到非 ASCII 时，若配置允许，改走剪贴板：`ClientCutText` 写文本 → `Ctrl+V`。
- **FR-002**: 剪贴板通道失败时回退为 `UNSUPPORTED` 并说明原因，不静默丢弃。
- **FR-003**: 新增参数（如 `input_mode=auto|keysym|clipboard`），默认 `auto`。
- **FR-004**: 远端剪贴板被覆盖属于可接受副作用，需在文档中写明。

## 验证计划

- 中文串粘贴后 `describe` 回读一致；
- 断开/不支持 `ClientCutText` 的服务端返回 `UNSUPPORTED`。
