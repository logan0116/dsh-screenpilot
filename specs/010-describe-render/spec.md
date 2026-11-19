# Feature Specification: describe 渲染元素清单

**Feature Branch**: `010-describe-render`

**Created**: 2026-11-19

**Status**: Implemented

**Input**: 需求 010-AR（cnc_nexus 现场反馈，`cnc_nexus/.ms-run/screenpilot-improvements.md` 问题1）。`tool()` 的 `output.render` 只渲染 `summarize()`，模型只看到 `capture=... | texts=175`，`data.texts` 的 `[{text,x,y,score}]` 全部丢弃。

## 背景与问题证据

| 问题 | 证据 | 影响 |
|---|---|---|
| 清单不进模型视野 | `lib/index.js` 旧 `summarize()` 只拼 capture/texts 计数 | 无法按文字定位，只能读截图目测坐标 |
| 目测坐标偏得离谱 | cnc_nexus 实测同一元素目测(727,543)、OCR(636,575)，差90px，点击落空 | 「按文字点击」这条核心能力等于废掉 |
| 全量渲染会撑爆上下文 | 现场一次 166–175 条 | 需要默认截断 |

## Clarifications

- Q: 渲染清单还是加 `screen_find`？ → A: 渲染清单 + `limit`。理由：`screen_act` 已用文字定位并返回命中/候选，`find` 会是第三种问同一件事的接口；而 describe 真正缺的是「画面上有什么」的全局视野，OCR 读错字时只回命中项反而更难排查。
- Q: 排序与条数？ → A: 按 `y` 再 `x`（阅读序），默认 40 条，`limit` 可调到 200，`0` 只回摘要。
- Q: 大小上限？ → A: 4000 字符硬上限，逐行累加判断，超了就停。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 模型能直接读到文字与坐标 (Priority: P1)

`screen_describe` 的渲染文本里逐行给出 `[序号] 文本 (x,y) 置信度`。

**Independent Test**: 用合成 `texts` 调 `output.render`，顺序为 `y` 升序、同 `y` 时 `x` 升序。

**Acceptance Scenarios**:

1. **Given** texts 为 `乙(200,300) 甲(10,100) 丙(5,100)`，**When** 渲染，**Then** 顺序为 丙(5,100)、甲(10,100)、乙(200,300)。
2. **Given** 200 条 texts，**When** 默认渲染，**Then** 只出 40 条、总字节 ≤4000。
3. **Given** `limit=0`，**When** 渲染，**Then** 只回摘要行（`capture=... | texts=N`）。
4. **Given** 真实台架 68 号机，**When** `screen_describe`，**Then** 渲染文本含 `[0] … (x,y) …` 且字节数 <4KB。

## Requirements *(mandatory)*

- **FR-001**: `summarize()` 保持原样用于其它工具；describe 用独立渲染器。
- **FR-002**: 排序按 `y` 升序、同 `y` 按 `x` 升序（阅读序，不按 score）。
- **FR-003**: 新增 `limit` 参数，默认 40，范围 0–200。
- **FR-004**: 渲染总长 ≤4000 字符，超出即截断，不截半行。
- **FR-005**: 失败信封的渲染与原来一致（只回 `FAIL code: message | hint`）。

## 非目标

- 新增 `screen_find` 工具（理由见 Clarifications）。
- 把坐标换成区域相对坐标。

## Success Criteria *(mandatory)*

- **SC-001**: 现场 166 条文本的渲染输出约 1.4KB、41 行，模型可直接读坐标点击。
- **SC-002**: 合成 200 条时输出 ≤4000 字节且不超过 40 条。
