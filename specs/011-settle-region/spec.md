# Feature Specification: settle 区域判稳与容差

**Feature Branch**: `011-settle-region`

**Created**: 2026-11-19

**Status**: Implemented

**Input**: 需求 011-AR（cnc_nexus 现场反馈，问题2）。68 号机 JISHU-Edge 每 10 秒刷心跳、HMI 坐标数值持续跳变，`settle --timeout 8` 稳定报 `TIMEOUT: 画面未稳定`；而 `act` 内部固定 sleep 1.2 秒反而能用。

## 背景与问题证据

| 问题 | 证据 | 影响 |
|---|---|---|
| 全屏逐字节比较 | 旧 `settle` 用 `image.tobytes() == prev.tobytes()` | 任何一处像素变化都判「未稳定」 |
| 持续刷新画面必然超时 | 68 号机心跳 10s、坐标区跳变 | `settle` 成了不可用操作，只能盲目 sleep |
| 超时只回 TIMEOUT | 旧 `_fail` 不带数据 | 调用方不知道「差多少」，无法自行判断 |
| 抓帧总是整屏 | `_read_frame` 固定请求 `0,0,w,h` | 判稳一个小区域也要传整帧，慢 |

## Clarifications

- Q: 三条方案（region / 容差 / 超时回帧）要不要只选一条？ → A: 全做。三者互补：region 躲开无关刷新，容差容忍抖动，超时回帧保证可诊断。
- Q: 容差默认多少？ → A: 0.002（0.2%），按差异像素占比，忽略单像素差值 ≤8 的抗锯齿噪声。
- Q: 区域判稳时 `_last` 要不要覆盖？ → A: 不覆盖。`_last` 是后续 `act`/`verify` 的坐标基准，必须保持整屏；只有整屏判稳才更新。
- Q: region 越界？ → A: `OUT_OF_BOUNDS`，不静默裁切。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 只关心的一块稳定就算稳定 (Priority: P1)

`settle(region=...)` 只比较该区域，区域外心跳刷新不影响判定。

**Independent Test**: 合成两张图，区域内完全相同、区域外黑白互换 → `stable=true`、`changedRatio=0`。

**Acceptance Scenarios**:

1. **Given** 区域外变化明显、区域内一致，**When** `settle(region)`，**Then** `ok=true`、`data.stable=true`、`changedRatio ≤ tolerance`。
2. **Given** 区域内持续变化，**When** `settle(region, timeout=0.2)`，**Then** `ok=false`、`error.code=TIMEOUT`、`data.changedRatio>tolerance`、`capture` 非空。
3. **Given** 画面变化 1%、tolerance=0.05，**When** `settle`，**Then** 判稳定；同图 tolerance=0.002 时判不稳定。
4. **Given** `region=(50,50,200,200)` 而画面 100×100，**When** `settle`，**Then** `error.code=OUT_OF_BOUNDS`。
5. **Given** 指定 region，**When** 抓帧，**Then** 实际请求的是该矩形（假 RemoteScreen 记录到的 region 全部等于入参）。

### User Story 2 - 超时也能自证 (Priority: P1)

超时信封带最后一帧证据与 `changedRatio`，调用方可以据此判断「再等等」还是「界面真的在动」。

**Acceptance Scenarios**:

6. **Given** 持续变化的画面，**When** 超时，**Then** 信封 `capture` 指向最后一帧文件，`data` 含 `changedRatio`/`tolerance`/`region`。

### User Story 3 - 现场可用性 (Priority: P2)

68 号机心跳界面上，区域 settle 3 秒内返回稳定。

**Acceptance Scenarios**:

7. **Given** 68 号机当前界面，**When** `screen_settle(region="160,680,910,1200")`，**Then** ≤3 秒返回 `stable=true`。

## Requirements *(mandatory)*

- **FR-001**: `settle` 增加 `region` 与 `tolerance` 参数，默认 `tolerance=0.002`。
- **FR-002**: 判稳依据是差异像素占比（单像素差值 >8 才计），不再是逐字节相等。
- **FR-003**: `region` 只影响判稳与抓帧范围；`region` 判稳不更新 `_last`。
- **FR-004**: 超时信封带 `capture` 与 `data.changedRatio/tolerance/region`。
- **FR-005**: `RemoteScreen.snapshot` 支持按矩形抓帧，越界抛 `ValueError` 并由协议层转 `OUT_OF_BOUNDS`。
- **FR-006**: 工具层 `screen_settle` 暴露 `region`/`tolerance`，CLI 与 daemon 透传。

## 非目标

- 增量更新与帧缓冲差分（RFB Incremental）。
- `describe` 改用区域抓帧（坐标基准会变，另立需求）。

## Success Criteria *(mandatory)*

- **SC-001**: 68 号机区域 settle ≤3 秒返回稳定（实测 2.63 秒）。
- **SC-002**: 超时信封可读到 `changedRatio` 与最后一帧。
- **SC-003**: `python -m unittest discover -p "test_*.py"` 全绿（15 条）。
