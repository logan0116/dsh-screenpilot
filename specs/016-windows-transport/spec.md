# Feature Specification: Windows 传输层回退（TCP + 端口文件 + token）

**Feature Branch**: `016-windows-transport`

**Created**: 2026-11-19

**Status**: Draft

**Input**: 需求 016-AR（cnc_nexus 同事 Windows 反馈第1/7/8条）。Windows 没有 `AF_UNIX`，常驻 sidecar 直接不可用，插件退化为"每次调用重新 spawn + 冷加载 OCR"。

## 背景与问题证据

| 问题 | 证据 | 影响 |
|---|---|---|
| 无 AF_UNIX 直接失败 | `python/client.py:29` 抛 `DaemonError`；`python/daemon.py:113` 硬用 `AF_UNIX` | Windows 上常驻会话不可用 |
| 残留端口文件不探活 | `python/client.py:97` 只 unlink 不查 pid | TCP 化后需先撞死端口再 spawn，多一次失败往返 |
| TCP 无认证 | （新引入面） | 同机任意进程可连 daemon 操控屏幕 |

## Requirements（草案）

- **FR-001**: 有 `AF_UNIX` 时行为不变；无 `AF_UNIX` 时 daemon 绑 `127.0.0.1:0` 随机端口。
- **FR-002**: 端口文件复用原 socket 路径，内容 `{port, pid, token, started}`；client 读它连接。
- **FR-003**: 连接必须带一次性 token（握手首行校验），不匹配立即断开。
- **FR-004**: client 连接前探活 pid，进程不存在则清理端口文件并走 spawn。
- **FR-005**: 连接超时用完整值（不走短超时兜底），因为首次 OCR 加载可能 >10 秒。
- **FR-006**: 协议与信封完全不变。

## 验证计划（需 Windows 环境）

- 在中文 Windows + uv Python 环境装插件，确认 `screen_start/describe/act/verify/settle/stop` 全链路可用；
- 同机另一个进程不带 token 连接 → 被拒；
- 杀掉 daemon 留下端口文件 → 下次调用自动清理并重建。

> 本需求无法在当前 Linux 环境自证，验收需同事在 Windows 回测。
