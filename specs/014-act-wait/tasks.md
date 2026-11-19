# Tasks: act 自适应等待

**Feature**: `014-act-wait` · 需求 `014-AR` · 目标版本 `v0.4.0`

## 实现

- [X] T1 `screen_protocol.act`：`sleep(1.2)` 改为 `wait`（默认 0.6，实测 0.4 收益不抵风险），参数可覆盖。
- [X] T2 动作后比对前后帧差异占比（复用 `_changed_ratio`）；补帧改为 **opt-in**（默认关）。
- [X] T3 补帧留证据 `<kind>_after2`，`data.retried=true`。
- [X] T4 `wait`/`retry_on_no_change` 透传：daemon args → CLI `--wait`/`--retry-on-no-change` → 工具层参数。

## 验证

- [X] V1 基线：改动前 `act` 四次均 2.71–2.74 秒。
- [X] V2 改动后 `act`（空区 xy 点击）四次：2.12/2.26/2.14/2.09，中位 2.13 秒，**-21%**。
- [X] V3 无变化点击 2.13 秒 ≤ 基线 2.71 秒；开启补帧会到约 3.5 秒，故默认关闭。
- [X] V4 `act` 后 `verify --kind changed` 返回 `diff=0`，未报「没有可比的前一帧」。

## 实测结论与偏差

- 原计划「无变化就补帧」在所有场景都做，实测**反而变慢**（3.52–3.62 秒 vs 2.71 秒），因为每次抓帧约 1.2 秒；已改为默认关闭、`retry_on_no_change=true` 时启用。
- 文本点击的耗时要额外加 OCR 定位（约 2 秒），与本次改动无关。
- 单测：`python/test_act_wait.py` 4 条（默认单帧、无变化补帧、已变化不补、wait 回传），全量 43 条 PASS。
