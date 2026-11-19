# Feature Specification: 输入覆盖（ASCII 全键位 + 非 ASCII 明确拒绝）

**Feature Branch**: `007-input-coverage`

**Created**: 2026-11-19

**Status**: Draft

**Input**: 需求 007-AR。`type_text` 只有 9 个符号的映射表，其余字符直接 `tap(ord(ch))`：ASCII 里需要 Shift 的符号（`!@#{}"<>?~` 等）发错键，非 ASCII（中文）把 Unicode 码点当 keysym 发，屏幕收不到任何字符且不报错。

## 背景与问题证据

| 问题 | 证据 | 影响 |
|---|---|---|
| Shift 符号发错 | 旧 `KEYSYM` 只含 `/` `.` `-` `\` `_` `:` `=` 与空格换行，其余符号（`!@#%&*(){}|"<>?~`）走 `tap(ord(ch))` | 密码、路径、JSON 片段无法输入 |
| 非 ASCII 静默失败 | `tap(ord("中"))` 发送 `0x4E2D`，X11 无此键码 | 中文输入"看起来成功"却什么都没输入 |
| 半个词落屏 | 若校验放在发送过程中，出错时前面字符已发出 | 现场状态被污染，难判断从哪重来 |
| 功能键缺失 | `KEYSYM` 只有 enter/esc/tab/backspace/win/方向/f5 | `f1`–`f12`、home/end/delete/pageup/pagedown 不可用 |

## Clarifications

### Session 2026-11-19

- Q: 中文怎么办？ → A: 本需求不做输入，明确 `UNSUPPORTED` 并给提示；剪贴板注入另立需求。
- Q: 为什么整串先校验？ → A: 输入是副作用，不能「打一半再报错」；校验通过才发第一个键。
- Q: Shift 映射按什么布局？ → A: US 布局（与台架一致）；其它布局属后续需求。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - ASCII 全键位可用 (Priority: P1)

`type` 能正确输入可打印 ASCII（含需要 Shift 的符号）。

**Why this priority**: 路径、密码、命令行参数都含 Shift 符号；缺了它输入能力不完整。

**Independent Test**: 用捕获式假连接验证 `A!z?1` 发送的 keysym 序列为 `shift+a`、`shift+1`、`z`、`shift+/`、`1`。

**Acceptance Scenarios**:

1. **Given** 文本 `A!z?1`，**When** `type`，**Then** keysym 序列为 `shift+a`、`shift+1`、`z`、`shift+/`、`1`。
2. **Given** 文本 `a b/c:d_e`，**When** `type`，**Then** 空格、`/`、`_` 直发，`:` 走 `shift+;`。
3. **Given** 真实台架搜索框已聚焦，**When** `type abc123` 两次再 `type zz9`，**Then** 画面 OCR 读到的搜索框文本末尾出现 `zz9`（证明字符确实落屏）。
4. **Given** 文本 `~{}|<>?@#$%^&*()`，**When** `type`，**Then** 每个字符都走对应 Shift 组合，不出现直发码点。

### User Story 2 - 非 ASCII 拒绝而不是静默失败 (Priority: P1)

含中文/带音标/emoji 的文本返回 `UNSUPPORTED`，且一个键都不发。

**Why this priority**: 静默失败最难排查——调用方以为输入了，实际没有。

**Independent Test**: `type 测试中文` → `UNSUPPORTED`，`error.message` 给出码点；假连接事件数为 0。

**Acceptance Scenarios**:

5. **Given** 文本 `中文`，**When** `type`，**Then** `ok=false`、`error.code=UNSUPPORTED`，事件数 0。
6. **Given** 文本 `café`，**When** `type`，**Then** `UNSUPPORTED`（`é`），且前面的 `caf` 也没被输入（原子性）。
7. **Given** emoji `😀`，**When** `type`，**Then** `UNSUPPORTED`，`error.message` 含 `U+1F600`。

### User Story 3 - 常用功能键可用 (Priority: P2)

`key` 支持 `f1`–`f12`、`home`/`end`/`delete`/`insert`/`pageup`/`pagedown`/`space`。

**Acceptance Scenarios**:

8. **Given** `key=f12`，**When** 执行，**Then** 发送 keysym `0xFFC9`；`key=pagedown` → `0xFF56`。

## Requirements *(mandatory)*

- **FR-001**: 可打印 ASCII（0x20–0x7E）直接以码位作 keysym；需要 Shift 的符号按 US 布局映射到基础键。
- **FR-002**: `type` 整串先校验，任一字符非 ASCII 则返回 `UNSUPPORTED` 且不发送任何键。
- **FR-003**: 错误信息含具体字符与码点，提示指向剪贴板注入（未实现）。
- **FR-004**: `key` 名映射补充 `f1`–`f12`、`home`/`end`/`insert`/`delete`/`pageup`/`pagedown`/`space`。
- **FR-005**: 换行与制表符仍可输入（`\n` → 0xFF0D，`\t` → 0xFF09）。

## 非目标

- 中文/emoji 输入（需剪贴板通道）。
- 非 US 键盘布局。

## Success Criteria *(mandatory)*

- **SC-001**: Shift 符号与功能键的 keysym 序列符合 US 布局。
- **SC-002**: 非 ASCII 文本零输入、返回 `UNSUPPORTED`。
- **SC-003**: 真实台架键入的字符能被 OCR 读回。
