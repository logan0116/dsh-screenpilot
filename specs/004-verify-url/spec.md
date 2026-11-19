# Feature Specification: verify 支持 url 断言

**Feature Branch**: `004-verify-url`

**Created**: 2026-11-19

**Status**: Draft

**Input**: 需求 004-AR。工具描述声明 `screen_verify` 支持 `kind=url`，协议层只有 `text/absent/changed`，传 url 直接落到 `PROTOCOL_ERROR`。

## 背景与问题证据

| 问题 | 证据 | 影响 |
|---|---|---|
| 工具描述与实现不一致 | `lib/index.js` 的 description 写「kind=text/absent/url/changed」；`screen_protocol.py` 的 `verify` 无 url 分支 | 调用方按文档使用会得到「未知断言」错误 |
| 缺少可判定的语义 | 画面里没有「地址栏」概念 | 简单当成 `text` 断言会把「URL 不在画面」误报为「URL 不匹配」 |

## Clarifications

### Session 2026-11-19

- Q: vnc 后端怎么拿到 URL？ → A: 只能靠 OCR 画面文字。断言 = 画面文字里是否出现该 URL 片段（忽略空白/全角/大小写/`http(s)://` 前缀）。
- Q: 画面里根本没有 URL 形态文本时怎么办？ → A: 返回 `UNSUPPORTED`，说明「无法定位地址栏」，而不是给一个假的 `satisfied=false`。
- Q: 命中多个怎么办？ → A: `satisfied=true`，并在 `data.hits` 里返回前 3 个命中的文本。
- Q: `value` 为空？ → A: `PROTOCOL_ERROR`，提示需要传 URL 片段。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 按画面文字判断 URL (Priority: P1)

画面有地址栏或任何含 URL 的文本时，`verify --kind url --text <片段>` 能回答「该片段是否在画面上」。

**Why this priority**: 工具表承诺了这个能力，且它是 `text` 断言之外唯一与「所在页面」相关的判断。

**Independent Test**: 用合成文本验证：画面含 `http://192.168.1.155:8090/skills`，断言 `192.168.1.155:8090` → `satisfied=true`；断言 `10.0.0.1:8080` → `satisfied=false`。

**Acceptance Scenarios**:

1. **Given** 画面文字含 `http://192.168.1.155:8090/skills`，**When** 断言 `192.168.1.155:8090`，**Then** `ok=true`、`data.satisfied=true`。
2. **Given** 画面文字含地址栏但指向别的地址（`http://10.0.0.1:8080/x`），**When** 断言 `192.168.1.155:8090`，**Then** `ok=true`、`data.satisfied=false`。
3. **Given** 断言值与画面文本的 scheme、大小写不同（画面 `HTTPS://Example.COM/Path`，断言 `example.com/path`），**When** 执行，**Then** `satisfied=true`。
4. **Given** `value` 为空，**When** 执行，**Then** `ok=false`、`error.code=PROTOCOL_ERROR`。

### User Story 2 - 判不了就说判不了 (Priority: P1)

画面里没有任何 URL 形态文本时，明确返回 `UNSUPPORTED`，不伪装成「不匹配」。

**Why this priority**: `satisfied=false` 会让调用方以为「页面地址不对」而反复重试，掩盖真实原因。

**Independent Test**: 台架桌面（无地址栏）上执行 `verify --kind url --text 192.168.1.155:8090`，返回 `UNSUPPORTED`。

**Acceptance Scenarios**:

5. **Given** 画面文字只有「文件/桌面/设置」，**When** 断言任意 URL 片段，**Then** `ok=false`、`error.code=UNSUPPORTED`、`error.hint` 指向改用 `kind=text`。
6. **Given** 真实台架桌面（无浏览器地址栏），**When** 通过 CLI 执行 url 断言，**Then** 返回 `UNSUPPORTED`，且 `text` 断言不受影响。

## Requirements *(mandatory)*

- **FR-001**: `verify` 增加 `kind=url` 分支，支持可选 `region` 限定识别范围。
- **FR-002**: 匹配前归一化：去空白、全角转半角、小写、去 `http://` 与 `https://` 前缀（两侧都做）。
- **FR-003**: 命中返回 `data.satisfied=true` 与 `data.hits`（最多 3 条原始文本）。
- **FR-004**: 未命中但画面存在含 `://` 的文本 → `satisfied=false`；画面完全没有 `://` 文本 → `UNSUPPORTED`。
- **FR-005**: `value` 为空 → `PROTOCOL_ERROR`。
- **FR-006**: 不改变 `text`/`absent`/`changed` 的既有行为。

## 非目标

- 浏览器 DOM/URL 真值读取（需 `web://` 后端）。
- 地址栏区域的自动定位（当前按整屏或调用方给的 `region`）。

## Success Criteria *(mandatory)*

- **SC-001**: 合成文本的 5 个用例（含 scheme、大小写、不匹配、无 URL、空值）结论符合预期。
- **SC-002**: 真实台架无地址栏时返回 `UNSUPPORTED`，`kind=text` 仍正常。
