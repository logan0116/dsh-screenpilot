# Tasks: 解释器解析与启动可诊断

**Feature**: `008-python-bin` · 需求 `008-AR` · 目标版本 `v0.2.1`

## 实现

- [X] T1 `lib/index.js`：新增 `defaultPython()`，按 显式配置 > `SCREENPILOT_PYTHON` > 包旁 `.venv/bin/python` > `python3` 解析。
- [X] T2 `python/client.py`：新增 `_log_tail()`，拉起超时与「连接被无声关闭」时附带日志最后 3 行。
- [X] T3 日志读取失败返回「无日志」，不抛二次异常。
- [X] T4 README：补 `pythonBin` 解析顺序与 `SCREENPILOT_PYTHON`。

## 验证

- [X] V1 `node -e "...Config({}).pythonBin"` → `/home/mozinodey/PycharmProjects/dsh-screenpilot/.venv/bin/python`。
- [X] V2 `_log_tail` 单测：日志含 `ModuleNotFoundError: No module named 'numpy'` 时返回该行；无日志返回「无日志」。
- [X] V3 系统 python3 缺 numpy 的场景已复现（装插件前的默认解释器），改动后默认不再落到它。

## 待验证（需重启后确认）

- [ ] 重启 DSH 后 `screen_*` 六个工具是否注册成功、能否对台架 192.168.1.68:5900 完成一次 `screen_start`。
