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
| `screen_stop()` | 释放会话：常驻进程退出、socket 与会话文件清理；无会话时返回 `NOT_STARTED` |

`target` 目前只支持 `vnc://host:port`。`web://url` 后端待接入。

## 依赖

Python 侧边车负责 RFB、OCR 与协议实现：

```bash
pip install -r python/requirements.txt
```

`rapidocr-onnxruntime` 会带 onnxruntime，首次运行加载模型约两秒。建议单独建虚拟环境。

## 安装

```bash
git clone git@github.com:<owner>/dsh-screenpilot.git
cd dsh-screenpilot

# sidecar 的依赖装进仓库内的 .venv（已 gitignore）；插件默认就用它
python3 -m venv .venv
.venv/bin/pip install -r python/requirements.txt

# 本地目录安装是 link:，需要让插件目录能解析到 DSH 自带的 peer 依赖
./scripts/link-peers.sh          # 或用 DSH_RUNTIME=<运行时目录> 指定

dsh plugin --profile <profile> add "$PWD"
```

装完重启 DSH，会话里应出现 6 个 `screen_*` 工具。

> `scripts/link-peers.sh` 做的事：把 `@deepseek-ai/dsh-tools`、`schemastery`、`cordis`
> 从你的 DSH 运行时软链到本仓库 `node_modules/`。这些包随 dsh 分发、不在 npm 公共仓库，
> link 安装时 Node 会从仓库真实路径解析，链不到就会在重启后加载失败
> （`Cannot find package '@deepseek-ai/dsh-tools'`）。换 DSH 运行时目录后重跑一次即可。

也可以只改 profile 的 `cordis.patch.yml`：

```yaml
- insert:
    - id: screenpilot
      name: "dsh-screenpilot"
```

## 配置

| 字段 | 默认 | 说明 |
|---|---|---|
| `pythonBin` | 见下 | 运行 sidecar 的解释器，需装有 requirements |
| `defaultTarget` | `vnc://192.168.1.68:5900` | 会话文件缺失时的兜底目标 |
| `timeoutMs` | `120000` | 单次 CLI 调用超时 |
| `vncPassword` | 空 | 服务端要求 VNC Authentication 时的密码；经环境变量传给 sidecar，不进命令行 |

`pythonBin` 的默认值按四级解析：显式配置 > `SCREENPILOT_PYTHON` > 包旁 venv >
`python3`。包旁 venv 同时探测 POSIX 的 `.venv/bin/python` 与 Windows 的
`.venv/Scripts/python.exe`。其它机器请先 `pip install -r python/requirements.txt`
或设 `SCREENPILOT_PYTHON`。

## Windows

- 传输层自动回退：没有 `AF_UNIX` 时 sidecar 绑 `127.0.0.1` 随机端口，
  并把 `{transport,port,pid,token}` 写到原 socket 路径；连接必须带一次性 token，
  同机其它进程不能静默接管。
- 解释器：uv 装的 Python 常常不向 `py` launcher 注册，`py -3` 会报
  `No suitable Python runtime found`。直接用 venv 的绝对路径最稳：

  ```yaml
  pythonBin: C:\path\to\dsh-screenpilot\.venv\Scripts\python.exe
  ```
- 编码：插件已内置 `PYTHONUTF8=1` 与标准流 `reconfigure(utf-8)`，中文 Windows
  的 GBK 代码页不再导致信封乱码。
- 首调耗时：sidecar 启动后会在后台预热 OCR，但第一次 `describe` 仍可能数秒到
  十数秒；这是模型推理本身，不是连接卡死。

环境变量 `SCREENPILOT_EVIDENCE` 指定截图目录，默认写到 `python/evidence/`；
`SCREENPILOT_STATE` 指定会话文件，默认 `~/.cache/screenpilot/session.json`；
`SCREENPILOT_IDLE` 指定常驻进程空闲退出秒数，默认 600。

## 常驻会话

每个目标（`host:port`）对应一个常驻 python 进程，通过 Unix domain socket 通信，
首个调用时按需拉起。好处是跨调用保留最近两帧（`verify --kind changed` 因此可用）、
`act` 的 `before` 直接复用上一帧、OCR 模型只加载一次。

- socket 与日志在 `SCREENPILOT_STATE` 同目录：`daemon-<host>-<port>.sock` 与 `.sock.log`；
- 空闲超过 `SCREENPILOT_IDLE` 秒自动退出并清理 socket；
- 进程崩了或残留 socket，下次调用会清理并重新拉起；
- 内部命令 `shutdown` 用于主动关停（工具层 `screen_stop` 见 003）；
- Windows 暂不支持 Unix domain socket，常驻会话不可用（返回 `NO_CONNECTION`）。

## 目标解析

优先级：`screen_start` 的 `target` > 会话文件（最近一次成功的 `screen_start`）>
配置 `defaultTarget` > 内置缺省。输出的 `screen.source` 会写明实际用的是哪一级
（`target`/`session`/`default`/`builtin`），排查"连的是哪台台架"先看这个字段。

服务端要求认证时（RFB 安全类型 2），客户端用 `vncPassword` 做 DES 质询-应答；
没配密码或密码错误返回 `NO_CONNECTION` 并说明原因。认证依赖 `cryptography`
（`pip install -r python/requirements.txt` 会装上）。

目标格式只接受 `vnc://host[:port]`，端口缺省 5900。缺 scheme、host 为空、
端口越界返回 `PROTOCOL_ERROR` 且不发起连接；非 `vnc` scheme 返回 `UNSUPPORTED`。

## 组合键与输入法

`screen_act(kind=key, value=...)` 支持组合键：`ctrl+space`、`alt+f4`、`ctrl+shift+s`；
也支持单按修饰键（`shift`）。解析与校验在发送前完成，未知修饰键或主键返回
`PROTOCOL_ERROR` 且不产生任何输入。

```text
可用修饰键：alt / cmd / control / ctrl / meta / option / shift / super / win
```

**中文输入法下的 `type` 不可靠**：工具只能发 ASCII keysym，输入法会把它们当拼音
组合（实测 `abc` 可能上屏成汉字候选）。正确做法是先用组合键把输入法切到英文
（常见 `shift`、`ctrl+space`、`win+space`，取决于机器配置），再 `type`，
并且用 `screen_verify` 回读一次确认原文真的落屏。中文/emoji 输入仍不支持（返回 `UNSUPPORTED`）。

## 协议

工具语义遵循 rsp/2：统一信封、封闭错误码（`NO_CONNECTION`、`NOT_STARTED`、
`UNSUPPORTED`、`NOT_FOUND`、`AMBIGUOUS`、`OUT_OF_BOUNDS`、`TIMEOUT`、
`PROTOCOL_ERROR`），每个 `act` 产动作前后两帧证据。

两条硬规则：每个动作必须留证；判定必须有确定性依据，视觉相似度只作辅证。

## 当前状态

- v0.2.0（2026-11-19）：6 项需求落地——`target` 四级优先级与会话文件、
  常驻 sidecar 与跨调用帧缓存、`screen_stop`、`verify --kind url`、
  RFB 编码兼容与错误分类、ASCII 全键位输入与非 ASCII 拒绝；
  六个工具与实现一一对应，`screen.source`/`pid`/`cost` 可观测；
- v0.3.0（2026-11-19）：6 项落地——VNC Authentication（安全类型 2）、
  解释器四级解析与启动日志回传、按键解析健壮性、`describe` 渲染元素清单、
  `settle` 区域判稳与容差、组合键与输入法路径；并修复 BUG-01（失败信封
  `capture=null` 被输出校验拦掉）。v0.2.1 未单独发布，内容并入本版；
- 已知用例耦合：`protocol_selftest.py` 的 12 条按旧台架布局写死坐标，
  台架画面变化后 P01–P06 会失败；
- 侧边栏观察窗未做（需要 Client 侧代码）；
- `web://` 后端未接入；
- 图标与设置页为占位。
