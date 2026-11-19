# Tasks: 冷启动预热

**Feature**: `017-ocr-prewarm` · 需求 `017-AR` · 目标版本 `v0.5.0`

- [X] T1 daemon 启动后后台线程预热 OCR。
- [X] T2 回包带 `data.ocr_ready`。
- [X] T3 README 写明首调耗时预期。
- [X] V1 实测 `ocr_ready` false→true（3 秒内），首调 `describe` 不超时。
