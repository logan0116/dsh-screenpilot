# Tasks: 按键解析健壮性

**Feature**: `009-keysym-robustness` · 需求 `009-AR` · 目标版本 `v0.3.0`

> 本条由 cnc_nexus 验收现场直接修掉并提交（`91b47ed`），此处补齐任务清单与看板登记。

## 实现

- [X] T1 `KEY_ALIASES`：`escape`/`return`/`page_up`/`pgdn`/`arrowup` 等常见写法归一到规范名。
- [X] T2 `resolve_keysym`：别名 → `KEYSYM` → 单字符可打印 ASCII 码位；无法识别返回 `None`。
- [X] T3 `act(kind=key)`：未识别时返回 `PROTOCOL_ERROR` 并列出可用按键，绝不静默降级。
- [X] T4 `daemon.handle` 兜底：处理异常转成 `PROTOCOL_ERROR` 信封，不再让常驻进程退出。

## 验证

- [X] V1 `python/test_key_robustness.py` 覆盖别名、未知键、单字符、异常兜底（假 RemoteScreen，不连真机）。
- [X] V2 全量单测 39 条 PASS（含本需求 141 行测试）。
- [X] V3 现场：`key=escape` 不再触发 `KeyError` 杀死 daemon。
