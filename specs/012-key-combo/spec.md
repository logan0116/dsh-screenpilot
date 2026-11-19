# Feature Specification: 组合键与输入法路径

**Feature Branch**: `012-key-combo`

**Created**: 2026-11-19

**Status**: Implemented

**Input**: 需求 012-AR（cnc_nexus 现场反馈，问题3）。68 号机默认中文输入法，`type "abc"` 上屏成候选汉字，`type "chcp 65001"` 变「产成品65001」；需要输入文字的步骤只能放弃。同时工具不支持任何组合键，连「切输入法」这种自救手段都没有。

## 背景与问题证据

| 问题 | 证据 | 影响 |
|---|---|---|
| 无组合键 | 旧 `act(kind=key)` 只接受单个键名/字符 | `ctrl+space`、`alt+f4`、`ctrl+shift+s` 全不可用 |
| 输入法无法自救 | 现场 5 种组合都发不出来 | 切不到英文，`type` 全部作废 |
| 单独修饰键被误判 | 旧逻辑把 `shift` 当"缺主键"（本次实现中现场实测发现） | 单按 Shift 切中英文失败 |

## Clarifications

- Q: 组合键语法？ → A: `mod[+mod...]+key`，大小写不敏感；`ctrl`/`control`、`alt`/`option`、`win`/`meta`/`super`/`cmd` 互为别名。
- Q: 校验时机？ → A: 整串解析在发送前完成，未识别修饰键/主键/多主键一律 `PROTOCOL_ERROR`，零副作用。
- Q: 单按修饰键怎么算？ → A: 合法按键（`shift` → 0xFFE1），不当"缺主键"。
- Q: 输入法怎么处理？ → A: 不猜机器配置。提供组合键让调用方自己切，README 明确「中文输入法下 type 不可靠，切英文后再 type 并 verify 回读」。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 组合键可用且可断言 (Priority: P1)

**Independent Test**: 假 RemoteScreen 捕获事件，`alt+f4` 的事件序列为 `down alt → down f4 → up f4 → up alt`。

**Acceptance Scenarios**:

1. **Given** `value="alt+f4"`，**When** 执行，**Then** 事件序列为 down alt、down f4、up f4、up alt。
2. **Given** `value="ctrl+shift+s"`，**When** 解析，**Then** 修饰键为 `[ctrl, shift]`、主键为 `s`。
3. **Given** `value="shift"`，**When** 执行，**Then** 走单键 `tap(0xFFE1)`，不报错。
4. **Given** `value="ctrl+notakey"`，**When** 执行，**Then** `PROTOCOL_ERROR`、`hint` 列出可用修饰键、零事件。

### User Story 2 - 现场可切输入法 (Priority: P2)

68 号机上组合键能真实送到（`ok=true`），调用方据此切英文后再 type。

**Acceptance Scenarios**:

5. **Given** 68 号机，**When** `act(key=ctrl+space)`、`win+space`、`shift`、`ctrl+shift+s`，**Then** 四次均 `ok=true`（送达成功）。
6. **Given** 非法组合键，**When** 在真机执行，**Then** `PROTOCOL_ERROR` 且画面不变。

## Requirements *(mandatory)*

- **FR-001**: `parse_combo` 支持 `mod[+mod...]+key`，含别名；单按修饰键合法。
- **FR-002**: 校验先于任何 I/O；非法输入零副作用。
- **FR-003**: `RemoteScreen.key_combo` 单连接内按 修饰键 → 主键 → 逆序抬起 发送。
- **FR-004**: 错误 `hint` 同时列出可用修饰键与按键。
- **FR-005**: README 写明组合键用法与「中文输入法下 type 不可靠」的处置路径。

## 非目标

- 自动检测/切换输入法（依赖机器配置，不猜）。
- 剪贴板注入中文（另立需求）。

## Success Criteria *(mandatory)*

- **SC-001**: `python -m unittest discover -p "test_*.py"` 全绿（27 条，含 11 条组合键用例）。
- **SC-002**: 68 号机上四种组合键均返回 `ok=true`；非法组合键返回 `PROTOCOL_ERROR`。
- **SC-003**: 单按 `shift` 不报错（现场实测发现的缺陷已修）。
