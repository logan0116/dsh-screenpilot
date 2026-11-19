# Tasks: describe 的 OCR 提速

**Feature**: `015-ocr-speed` · 需求 `015-AR` · 目标版本 `v0.4.0`

## 实现

- [X] T1 `ocr_locator`：`frame_key()`（blake2b-12 指纹 + region）、`cached()`、`remember()`，容量 2。
- [X] T2 `find`/`find_all` 优先命中缓存；`describe` 识别后写入缓存。
- [X] T3 `describe` 增加 `mode`（`precise` 默认 / `fast` 整图单次），回包带 `mode`。
- [X] T4 `mode` 透传：daemon → CLI `--mode` → 工具层参数。

## 验证

- [X] V1 六种"能提速"的方案实测（整图/并行/更细列/降采样/检测边长调优），均因丢小字或更慢被否，数据见 spec 背景表。
- [X] V2 同帧 `verify`：0.07 秒（原约 1.5 秒）。
- [X] V3 同帧 `act(text=…)`：2.29 秒（省掉一次 OCR）。
- [X] V4 `describe(mode=fast)`：2.50 秒 / 79 条；`precise`：4.79–8.66 秒 / 87–88 条。
- [X] V5 单测 `test_ocr_cache` 5 条 + 全量 48 条 PASS。

## 未解决（如实记录）

- **单次 `describe` 的精确模式仍是 4.5 秒量级**：这一项没有提速，因为任何"少扫一次"的方案都会丢小字号数字。
  再快只能换 OCR 模型/推理后端，属于另一条需求。
- `fast` 模式的召回损失（小数字）没有做量化验收，只在 spec 背景表里给了整图扫描的实测（保留 69%）。
