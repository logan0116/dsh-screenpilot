# Feature Specification: describe 的 OCR 提速（同帧缓存 + fast 模式）

**Feature Branch**: `015-ocr-speed`

**Created**: 2026-11-19

**Status**: Implemented

**Input**: 需求 015-AR。`describe` 单次约 5 秒，其中 OCR 约 4.5 秒（分列扫描 3 次）；cnc_nexus 现场反馈执行效率低。

## 背景与问题证据

| 方案 | 耗时 | 召回代价 | 结论 |
|---|---|---|---|
| 现状：3 列串行 | 4.5–8 秒 | 基准（85 框 / 78 去重文本） | — |
| 整图单次 | 1.4 秒 | 只保留 69%，漏 `120/20/200/308/60/80` 等小数字 | 否 |
| 整图 + `det_limit_side_len` 736→2560 | 1.4–3.6 秒 | 保留 69–74%，小数字仍漏 | 否 |
| 3 列并行（ThreadPool） | 4.90 秒 | 一致 | 否（比串行 4.53 秒更慢，onnxruntime 内部已多线程） |
| 更细的列（180/135px） | 12–20 秒 | 结果集变化 | 否 |
| 降采样 75% | 1.3 秒 | 保留 76%，丢的正是小数字 | 否 |

小字号数字是数控 HMI 的核心信息（坐标、计数、报警号），任何丢小字的方案都不可接受。

## Clarifications

- Q: 那还剩什么办法？ → A: 两条不改识别结果的：①同一帧不重复识别（缓存）；②让调用方显式选 `fast`。
- Q: 缓存会不会返回过期结果？ → A: 键是帧内容的 blake2b 指纹，画面一变必然失效；只保留最近 2 帧。
- Q: `fast` 会不会被误当默认？ → A: 默认 `precise`；`fast` 必须在参数里显式写，且回包带 `mode` 字段。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 同一帧不再重复识别 (Priority: P1)

describe 之后紧接着 verify/act（画面未变）时，第二次不再跑 OCR。

**Acceptance Scenarios**:

1. **Given** 刚 `describe` 过某帧，**When** 在同一帧上 `verify(text=…)`，**Then** 总耗时从约 1.5 秒降到 0.1 秒以内（实测 0.07 秒）。
2. **Given** 同一帧第二次查找，**When** 统计识别次数，**Then** 不再增加。
3. **Given** 画面已变化，**When** 查找，**Then** 重新识别（缓存不误命中）。
4. **Given** 两张不同帧先后出现，**Then** 各自有独立缓存条目。

### User Story 2 - 调用方可以显式选 fast (Priority: P2)

需要快速看布局时用 `mode=fast`（整图单次，约 1.4–2.5 秒），知道会漏小字。

**Acceptance Scenarios**:

5. **Given** `mode=fast`，**When** `describe`，**Then** 只做一次整图识别（`scan_calls=1`、`column_calls=0`）。
6. **Given** `mode=precise`（默认），**When** `describe`，**Then** 走分列扫描（`column_calls=1`）。

## Requirements *(mandatory)*

- **FR-001**: `TextLocator` 增加同帧缓存：键为帧内容指纹 + region，容量 2。
- **FR-002**: `find`/`find_all` 优先用缓存；`describe` 识别后写入缓存。
- **FR-003**: 缓存键必须包含画面内容哈希，画面变化即失效。
- **FR-004**: `describe` 增加 `mode`，取值 `precise`（默认）/`fast`，回包带 `mode`。
- **FR-005**: `mode` 透传 daemon → CLI `--mode` → 工具层参数。
- **FR-006**: 不改变 `precise` 的识别结果（分列参数不变）。

## 非目标

- 更换 OCR 模型或推理后端。
- 降低 `precise` 的召回以换速度。

## Success Criteria *(mandatory)*

- **SC-001**: 同帧 `verify` ≤0.1 秒（原约 1.5 秒）。
- **SC-002**: 同帧 `act(text=…)` 省掉一次 OCR（实测 2.29 秒，原约 3.4–4 秒）。
- **SC-003**: `mode=fast` 约 2.5 秒返回，且明确标注会漏小字。
