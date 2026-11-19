# Feature Specification: act 自适应等待（去掉固定 sleep）

**Feature Branch**: `014-act-wait`

**Created**: 2026-11-19

**Status**: Implemented

**Input**: 需求 014-AR。`act` 动作后固定 `time.sleep(1.2)` 再取帧，占单次点击 2.71 秒总耗时的 44%；而实际界面多数在 0.3 秒内就重绘完了。

## 背景与问题证据

| 项 | 实测（68号机，1080×1920） |
|---|---|
| `act(click)` 总耗时 | 2.71 / 2.74 / 2.71 秒（三次） |
| 其中固定 `sleep(1.2)` | 1.2 秒 |
| 其中动作后抓帧 | 约 1.2 秒 |

固定睡眠的坏处是两头都不对：界面已经变了还在等；界面没变时等完也不知道是否真的没变。

## Clarifications

- Q: 为什么不用 settle 判稳？ → A: settle 至少要两帧（约 2.2 秒），比现在的 1.2 秒更慢；抓帧成本决定了"多等一帧"很贵。
- Q: 等待多久合适？ → A: 默认 0.4 秒，可由 `wait` 参数覆盖。
- Q: 怎么区分"界面没变"和"还没重绘"？ → A: 先用变化占比判断；占比接近 0 时补一帧（+0.5 秒），保留变化更大的一帧。最坏情况仍然是两次抓帧，不比原实现更差。
- Q: 会不会破坏 `verify changed` 的前帧语义？ → A: 不会，`_prev` 仍指向动作前帧，`_last` 指向最终采纳的动作后帧。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 界面有反应时立刻返回 (Priority: P1)

点击导致界面变化时，不再白等 1.2 秒。

**Acceptance Scenarios**:

1. **Given** 点击会改变界面，**When** 执行 `act`，**Then** 总耗时明显低于 2.71 秒（目标 ≤1.8 秒）。
2. **Given** 同上，**When** 读回 `data.before`/`data.after`，**Then** 两帧都在，且 `after` 反映变化后的界面。

### User Story 2 - 界面没反应时也不假装 (Priority: P1)

点击不改变界面时，补一帧确认，不把"还没重绘"当成"没反应"。

**Acceptance Scenarios**:

3. **Given** 点击后画面几乎不变，**When** 执行 `act`，**Then** 仍返回成功，且 `data` 里标明是否补过帧（`retried=true`）。
4. **Given** 补帧后画面仍然不变，**Then** 耗时不超过原实现（约 2.7 秒量级）。

### User Story 3 - 前帧语义不被破坏 (Priority: P2)

**Acceptance Scenarios**:

5. **Given** 连续 `act` 后紧接着 `verify --kind changed`，**Then** 仍能正确比较，不报"没有可比的前一帧"。

## Requirements *(mandatory)*

- **FR-001**: `act` 的固定 1.2 秒等待改为可配置 `wait`，默认 0.4 秒。
- **FR-002**: 动作后取一帧，计算与动作前帧的差异占比；超过阈值直接返回。
- **FR-003**: 差异接近 0 时补一帧（等待 0.5 秒），保留与动作前帧差异更大的一帧作为 `after`。
- **FR-004**: 补帧时额外留一张证据（`<kind>_after2`），`data.retried=true`。
- **FR-005**: `_prev`/`_last` 语义保持不变。
- **FR-006**: `wait` 透传到工具层与 CLI（`--wait`）。

## 非目标

- 改变抓帧方式（RFB 增量更新另议）。
- OCR 提速。

## Success Criteria *(mandatory)*

- **SC-001**: 有变化的点击耗时 ≤1.8 秒（原 2.71 秒）。
- **SC-002**: 无变化的点击耗时不超过原实现。
- **SC-003**: `verify changed` 在 `act` 之后仍可用。
