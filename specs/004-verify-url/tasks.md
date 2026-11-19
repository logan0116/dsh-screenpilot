# Tasks: verify 支持 url 断言

**Feature**: `004-verify-url` · 需求 `004-AR` · 目标版本 `v0.2.0`

## 实现

- [X] T1 `screen_protocol.verify` 增加 `kind=url` 分支：整屏或 `region` 内 OCR，归一化后子串匹配。
- [X] T2 `_url_core()` 归一化助手：去空白、全角转半角、小写、去 `http(s)://`。
- [X] T3 三态分流：命中 → `satisfied=true` + `hits`；有地址栏但不同 → `satisfied=false`；无 `://` 文本 → `UNSUPPORTED`；空值 → `PROTOCOL_ERROR`。

## 验证

- [X] V1（合成文本，5 例全 PASS）
  - 带 scheme 的地址栏 + 省略 scheme 的断言 → `satisfied=true`
  - 地址栏存在但 URL 不同 → `satisfied=false`
  - 画面无 URL 形态文本 → `UNSUPPORTED`
  - `HTTPS://Example.COM/Path` 断言 `example.com/path` → `satisfied=true`
  - 空 value → `PROTOCOL_ERROR`
- [X] V2（真实台架 192.168.1.68:5900）桌面无地址栏：`verify --kind url --text 192.168.1.155:8090` → `UNSUPPORTED`，`error.message` 说明「没有可识别的地址栏或 URL 文本」。
- [X] V3 同台架 `verify --kind text --text 桌面` → `found=true`，`text` 断言未受影响。
