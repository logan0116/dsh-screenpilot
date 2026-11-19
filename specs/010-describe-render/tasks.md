# Tasks: describe 渲染元素清单

**Feature**: `010-describe-render` · 需求 `010-AR` · 目标版本 `v0.3.0`

## 实现

- [X] T1 `lib/index.js`：`tool()` 增加可选 `render` 参数，未传时仍用 `summarize`。
- [X] T2 新增 `describeText(args, value)`：按 `y,x` 排序、默认 40 条、4000 字符上限、`limit=0` 只回摘要。
- [X] T3 `screen_describe` 参数增加 `limit`，并挂自定义渲染器。

## 验证

- [X] V1 合成 3 条：输出顺序 丙(5,100) → 甲(10,100) → 乙(200,300)。
- [X] V2 合成 200 条：默认渲染 41 行（摘要+40 条）、1100 字节。
- [X] V3 `limit=0`：只回 `capture=x.png | texts=3`。
- [X] V4 真实台架 68 号机：166 条文本 → 渲染 1415 字节 / 41 行，首行 `[0] 口 (1008,20) 0.79`。
