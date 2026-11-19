# Tasks: settle 区域判稳与容差

**Feature**: `011-settle-region` · 需求 `011-AR` · 目标版本 `v0.3.0`

## 实现

- [X] T1 `screen_protocol.settle`：改为差异像素占比判稳（numpy，差值 >8 才计），增加 `region`/`tolerance`。
- [X] T2 `_fail` 支持 `capture` 与 `data`，超时回带最后一帧与 `changedRatio`。
- [X] T3 `RemoteScreen.snapshot(region=...)`：只请求目标矩形并返回区域图；越界抛 `ValueError`。
- [X] T4 `_read_frame` 支持矩形请求，Raw/CopyRect 坐标按矩形原点换算。
- [X] T5 `region` 判稳不覆盖 `_last`（保持 act/verify 的整屏坐标基准）。
- [X] T6 工具层 `screen_settle` 暴露 `region`/`tolerance`，daemon 与 CLI 透传。

## 验证

- [X] V1 `python/test_settle_region.py` 5 条单测全绿（区域外变化、持续变化超时、容差两档、越界、只请求区域）。
- [X] V2 `python -m unittest discover -p "test_*.py"`：15 条全 PASS。
- [X] V3 68 号机实测：`settle(region=160,680,910,1200)` 2.63 秒返回 `stable=true, changedRatio=0`。
- [X] V4 68 号机整屏 `settle(timeout=3)`：`TIMEOUT` + `changedRatio=0.08639`，说明整屏确实在动，区域判稳才是正确姿势。
