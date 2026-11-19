# Tasks: act 自适应等待

**Feature**: `014-act-wait` · 需求 `014-AR` · 目标版本 `v0.4.0`

## 实现

- [ ] T1 `screen_protocol.act`：`sleep(1.2)` 改为 `wait`（默认 0.4），参数可覆盖。
- [ ] T2 动作后比对前后帧差异占比（复用 `_changed_ratio`），接近 0 时补一帧并保留差异更大者。
- [ ] T3 补帧留证据 `<kind>_after2`，`data.retried=true`。
- [ ] T4 `wait` 透传：daemon args → CLI `--wait` → 工具层参数。

## 验证

- [ ] V1 基线：改动前 `act` 三次均为 2.71 秒。
- [ ] V2 有变化点击：耗时 ≤1.8 秒。
- [ ] V3 无变化点击：耗时不高于基线。
- [ ] V4 `act` 后 `verify --kind changed` 仍返回数值而非报错。
