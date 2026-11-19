# Feature Specification: 冷启动预热与首调可见性

**Feature Branch**: `017-ocr-prewarm`

**Created**: 2026-11-19

**Status**: Draft

**Input**: 需求 017-AR（同事反馈第4条）。daemon 首次 `describe` 要加载 OCR 模型，Windows 实测 >10 秒，README 未提示，容易被当成连接失败。

## Requirements（草案）

- **FR-001**: daemon 启动后台线程预热 OCR 引擎，不阻塞握手。
- **FR-002**: 预热未完成时的请求等待（有上限），不返回 TIMEOUT。
- **FR-003**: 信封里可通过 `data.ocr_ready` 观测预热状态。
- **FR-004**: README 写明首调耗时预期与超时建议。

## 验证计划

- 冷启动后立即 `describe`：总耗时仍含模型加载，但不会因超时失败；
- 第二次 `describe` 明显更快；
- `screen.pid` 稳定不变。
