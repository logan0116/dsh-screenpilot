# dsh-screenpilot

Agent 屏幕驾驶员：把远程屏幕操控封装成 `screen_*` 工具，让 agent 能看、能点、能断言，
并把每一步的截图留成证据。

与 [ego-browser](https://github.com/Fisfzy/dsh-ego-browser) 并列：它驱动浏览器页面，
本插件驱动整块屏幕（远程测试台桌面、桌面应用，后续也包括浏览器）。

## 工具

| 工具 | 作用 |
|---|---|
| `screen_start(target)` | 建立会话，返回 `backend` 与 `capabilities` |
| `screen_describe(region?)` | 取画面 + 元素清单（文本与坐标） |
| `screen_act(kind, by, value, region?)` | click / type / key / scroll，按文字或坐标 |
| `screen_verify(kind, value, region?)` | 断言文本存在、不存在、URL、画面变化 |
| `screen_settle(timeout?)` | 等画面稳定 |
| `screen_stop()` | 释放会话（预留） |

`target` 目前只支持 `vnc://host:port`。`web://url` 后端待接入。

## 依赖

Python 侧边车负责 RFB、OCR 与协议实现：

```bash
pip install -r python/requirements.txt
```

`rapidocr-onnxruntime` 会带 onnxruntime，首次运行加载模型约两秒。建议单独建虚拟环境。

## 安装

```bash
dsh plugin --profile web add /path/to/dsh-screenpilot
```

或在 profile 的 `cordis.patch.yml` 中加一行：

```yaml
- insert:
    - id: screenpilot
      name: "dsh-screenpilot"
```

## 配置

| 字段 | 默认 | 说明 |
|---|---|---|
| `pythonBin` | `python3` | 运行 sidecar 的解释器，需装有 requirements |
| `defaultTarget` | `vnc://192.168.1.68:5900` | 会话文件缺失时的兜底目标 |
| `timeoutMs` | `120000` | 单次 CLI 调用超时 |

环境变量 `SCREENPILOT_EVIDENCE` 指定截图目录，默认写到 `python/evidence/`；
`SCREENPILOT_STATE` 指定会话文件，默认 `~/.cache/screenpilot/session.json`。

## 目标解析

优先级：`screen_start` 的 `target` > 会话文件（最近一次成功的 `screen_start`）>
配置 `defaultTarget` > 内置缺省。输出的 `screen.source` 会写明实际用的是哪一级
（`target`/`session`/`default`/`builtin`），排查"连的是哪台台架"先看这个字段。

目标格式只接受 `vnc://host[:port]`，端口缺省 5900。缺 scheme、host 为空、
端口越界返回 `PROTOCOL_ERROR` 且不发起连接；非 `vnc` scheme 返回 `UNSUPPORTED`。

## 协议

工具语义遵循 rsp/2：统一信封、封闭错误码（`NO_CONNECTION`、`NOT_STARTED`、
`UNSUPPORTED`、`NOT_FOUND`、`AMBIGUOUS`、`OUT_OF_BOUNDS`、`TIMEOUT`、
`PROTOCOL_ERROR`），每个 `act` 产动作前后两帧证据。

两条硬规则：每个动作必须留证；判定必须有确定性依据，视觉相似度只作辅证。

## 当前状态

- v0.1.0：VNC 后端可用，六个工具与协议自测 12/12 通过；
- v0.2.0（进行中）：`target` 真正生效（四级优先级 + 会话文件），`screen.source` 可诊断；
  协议自测的 12 条用例按旧台架布局写死坐标，台架画面变化后 P01–P06 会失败，属已知的用例耦合；
- 侧边栏观察窗未做（需要 Client 侧代码）；
- `web://` 后端未接入；
- 图标与设置页为占位。
