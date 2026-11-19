# Feature Specification: 解释器解析与常驻进程启动可诊断

**Feature Branch**: `008-python-bin`

**Created**: 2026-11-19

**Status**: Draft

**Input**: 需求 008-AR。插件从本地目录安装（`link:`）后，`pythonBin` 仍是 `python3`；本机 `python3` 是 3.14 且没有 pillow/numpy/rapidocr，常驻进程起不来，调用方看到的是 15 秒超时后的 `NO_CONNECTION`，看不出真因。

## 背景与问题证据

| 问题 | 证据 | 影响 |
|---|---|---|
| 默认解释器不可用 | `lib/index.js` 旧默认 `python3`；`python3 -c "import numpy"` → `ModuleNotFoundError` | 装完即不可用 |
| 失败信息无真因 | `client.ensure` 超时只报「启动超时，见 xxx.log」 | 用户要自己翻日志才能发现是缺依赖 |
| 依赖只在 .venv | 仓库 `.venv`（Python 3.11）内有 pillow/numpy/rapidocr | 直连源码目录时默认解释器几乎必然缺依赖 |

## Clarifications

### Session 2026-11-19

- Q: 优先级怎么定？ → A: 显式配置 > `SCREENPILOT_PYTHON` 环境变量 > 包旁 `.venv/bin/python`（存在才用）> `python3`。
- Q: 为什么不把依赖装进系统 python？ → A: 本机 python3.14 太新，onnxruntime 等未必有轮子；且不应改动用户系统环境。
- Q: 日志要不要回传全部？ → A: 只回传最后 3 行、最多 400 字节，够看出异常类型即可。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 装上就能跑 (Priority: P1)

从源码目录安装插件后，默认解释器自动指向包旁 `.venv`，无需手工配 `pythonBin`。

**Independent Test**: `node -e "import('./lib/index.js').then(m=>console.log(m.Config({}).pythonBin))"` 输出 `.venv/bin/python` 的绝对路径。

**Acceptance Scenarios**:

1. **Given** 包目录下存在 `.venv/bin/python`，**When** 读取 `Config` 默认值，**Then** `pythonBin` 是该解释器的绝对路径。
2. **Given** 设置了 `SCREENPILOT_PYTHON=/opt/py/bin/python`，**When** 读取默认值，**Then** 返回该环境变量值（优先级高于 `.venv`）。
3. **Given** 显式配置 `pythonBin`，**When** 插件启动，**Then** 以显式配置为准。
4. **Given** 包目录下没有 `.venv`，**When** 读取默认值，**Then** 回落到 `python3`。

### User Story 2 - 启动失败能看出真因 (Priority: P1)

常驻进程起不来时，错误信息带上 daemon 日志尾部，直接看到 `ModuleNotFoundError` 之类的根因。

**Acceptance Scenarios**:

5. **Given** daemon 日志里有 `ModuleNotFoundError: No module named 'numpy'`，**When** 客户端等待超时，**Then** 错误信息包含该行。
6. **Given** 没有任何日志，**When** 等待超时，**Then** 错误信息显示「无日志」，不抛二次异常。

## Requirements *(mandatory)*

- **FR-001**: `pythonBin` 默认值按四级解析：显式配置 > `SCREENPILOT_PYTHON` > 包旁 `.venv/bin/python` > `python3`。
- **FR-002**: 四级解析只在默认值层实现，显式配置永远优先。
- **FR-003**: 客户端拉起超时或连接被无声关闭时，错误信息附带 daemon 日志最后 3 行。
- **FR-004**: 日志读取失败不得二次抛异常。
- **FR-005**: README 写明解析顺序与 `SCREENPILOT_PYTHON`。

## 非目标

- 自动安装 python 依赖。
- Windows 下的解释器探测。

## Success Criteria *(mandatory)*

- **SC-001**: 默认 `pythonBin` 指向 `.venv`，插件装完即可拉起常驻进程。
- **SC-002**: 缺依赖时错误信息含真实异常行。
