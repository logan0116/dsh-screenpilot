# dsh-screenpilot

Agent 屏幕驾驶员：把远程屏幕操控封装成 `screen_*` 工具，让 agent 能看、能点、能断言，
并把每一步的截图留成证据。

与 [ego-browser](https://github.com/Fisfzy/dsh-ego-browser) 并列：它驱动浏览器页面，
本插件驱动整块屏幕（远程测试台桌面、桌面应用，后续也包括浏览器）。

## 工具

| 工具 | 作用 |
|---|---|
| `screen_start(target?)` | 建立会话，返回 `capabilities` 与 `screen.source`（target/session/default/builtin） |
| `screen_describe(region?, limit?, mode?)` | 取画面 + 元素清单；渲染默认 40 条，`limit` 可调；`mode=fast` 整图单次（快但漏小字） |
| `screen_act(kind, by?, value?, region?, wait?, retry_on_no_change?, input_mode?)` | click / type / key / scroll；`wait` 控制动作后等待；`input_mode` 选键盘或剪贴板 |
| `screen_verify(kind, value?, region?)` | 断言 text / absent / url / changed；`data.satisfied` 才是结论 |
| `screen_settle(timeout?, region?, tolerance?)` | 等画面稳定；`region` 只在该区域判稳，超时回最后一帧与 `changedRatio` |
| `screen_stop()` | 释放会话：常驻进程退出、socket/端口文件与会话文件清理；无会话时返回 `NOT_STARTED` |

`target` 目前只支持 `vnc://host:port`。`web://url` 后端待接入。

## 依赖

Python 侧边车负责 RFB、OCR 与协议实现：

```bash
pip install -r python/requirements.txt
```

`rapidocr-onnxruntime` 会带 onnxruntime。sidecar 启动后会在后台预热 OCR，但**第一次
`describe` 仍可能数秒到十数秒**（Windows 上尤其明显）——这是模型推理，不是连接卡死。
建议单独建虚拟环境。

## 安装

```bash
git clone git@github.com:logan0116/dsh-screenpilot.git   # 无 SSH 用 https://github.com/logan0116/dsh-screenpilot.git
cd dsh-screenpilot

# sidecar 的依赖装进仓库内的 .venv（已 gitignore）；插件默认就用它
python3 -m venv .venv
.venv/bin/pip install -r python/requirements.txt
# Windows 用：.venv\Scripts\python.exe -m pip install -r python\requirements.txt

# 本地目录安装是 link:，需要让插件目录能解析到 DSH 自带的 peer 依赖
./scripts/link-peers.sh          # 或用 DSH_RUNTIME=<运行时目录> 指定

dsh plugin --profile web add "$PWD"     # web 换成你实际的 profile 名
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

每个目标（`host:port`）对应一个常驻 python 进程，首个调用时按需拉起。好处是跨调用
保留最近两帧（`verify --kind changed` 因此可用）、`act` 的 `before` 直接复用上一帧、
OCR 模型只加载一次。

- 传输：有 `AF_UNIX` 走 Unix domain socket；没有（Windows）自动回退到 `127.0.0.1`
  随机端口，并把 `{transport,host,port,pid,token}` 写到原 socket 路径，连接须带一次性 token；
- socket/端口文件与日志在 `SCREENPILOT_STATE` 同目录：`daemon-<host>-<port>.sock` 与 `.sock.log`；
- 空闲超过 `SCREENPILOT_IDLE` 秒自动退出并清理；
- 进程崩了或残留文件，下次调用按 pid 探活后清理并重新拉起；
- 内部命令 `shutdown` 用于主动关停（工具层 `screen_stop`）；
- 客户端中途断连不会带崩常驻进程（`BUG-02`）。

## 观察窗

装好后侧边栏/底部面板会出现「远程屏幕」标签（优先挂 `dsh-better-sidebar`，没有则用
宿主原生 `sidebarRightTabs`）。面板用 SSE 播放远端当前画面，并允许点击接管：

- 先调一次 `screen_start`，面板 1 秒内出首帧，顶部显示 `帧 <n> · <时间>`；
- 点击画面等价于 `screen_act(click, xy)`，坐标按降采样比例换算回原图；
- 帧率约 1 帧/秒，瓶颈是 RFB 每次全帧传输（1080×1920 约 8MB），不是渲染；
- host 侧路由在 `/api/screenpilot/{state,frame,stream,input}`，同源、需登录态；
- 无会话时面板提示「先调用 screen_start」，点击返回 `NOT_STARTED`。

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

**中文输入法下的 ASCII `type` 不可靠**：keysym 会被输入法当拼音组合（实测 `abc` 可能
上屏成汉字候选）。正确做法是先用组合键把输入法切到英文（常见 `shift`、`ctrl+space`、
`win+space`，取决于机器配置），再 `type`，并用 `screen_verify` 回读确认原文落屏。

**非 ASCII 文本走剪贴板**（`input_mode`）：

| 取值 | 行为 |
|---|---|
| `auto`（默认） | 含非 ASCII 时写远端剪贴板再发 `Ctrl+V`；纯 ASCII 仍逐键输入 |
| `keysym` | 只走键盘；遇非 ASCII 返回 `UNSUPPORTED` 且零副作用 |
| `clipboard` | 强制剪贴板通道（纯 ASCII 也可） |

注意：写远端剪贴板会**覆盖用户原本的剪贴板内容**；`Ctrl+V` 落在当前焦点所在的输入框，
在不熟悉的机器上先确认焦点。中文/emoji 目前只能经此通道，不保证所有服务端都接受
UTF-8 的 `ClientCutText`。

## 协议

工具语义遵循 rsp/2：统一信封、封闭错误码（`NO_CONNECTION`、`NOT_STARTED`、
`UNSUPPORTED`、`NOT_FOUND`、`UNSTABLE`、`OUT_OF_BOUNDS`、`TIMEOUT`、
`PROTOCOL_ERROR`），每个 `act` 产动作前后两帧证据。命中多个候选不是错误码，
而是 `data.ambiguous=true` + `data.candidates`。

两条硬规则：每个动作必须留证；判定必须有确定性依据，视觉相似度只作辅证。

## 当前状态

- v0.5.0（2026-11-20）：Windows 适配四项 + 两个线上 bug
  - `013-AR` 侧边栏观察窗：host 同源路由 + SSE 推帧，面板内可点击接管（约 1 帧/秒）
  - `014-AR` `act` 自适应等待：去掉固定 `sleep(1.2)`，单次点击 2.71s → 2.13s
  - `015-AR` OCR 同帧缓存 + `mode=fast`：同帧 `verify` 1.5s → 0.07s
  - `016-AR` Windows 传输层回退：无 `AF_UNIX` 时走 `127.0.0.1` 随机端口 + 一次性 token
  - `017-AR` OCR 预热：daemon 启动即后台加载模型，回包带 `data.ocr_ready`
  - `018-AR` 剪贴板输入：非 ASCII 文本走 RFB `ClientCutText` + `Ctrl+V`
  - `019-AR` Windows 文档与 `.venv/Scripts/python.exe` 探测
  - `BUG-02` 客户端断连不再带崩 daemon；`BUG-03` 中文 Windows 信封不再乱码
  - `v0.4.0` 未单独发布，内容并入本版
- 已知限制：
  - `protocol_selftest.py` 的 12 条按旧台架布局写死坐标，台架画面变化后 P01–P06 会失败；
  - 单次 `describe` 的精确模式仍约 5 秒（任何减少扫描次数的方案都会丢小字号数字）；
  - 观察窗约 1 帧/秒，流畅度受 RFB 全帧抓取限制；
  - `web://` 后端未接入；
  - Windows 上的传输层与剪贴板粘贴尚未真机验证；
  - 图标与设置页为占位。
