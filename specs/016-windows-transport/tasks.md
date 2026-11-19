# Tasks: Windows 传输层回退

**Feature**: `016-windows-transport` · 需求 `016-AR` · 目标版本 `v0.5.0`

- [X] T1 daemon：无 AF_UNIX 或 `SCREENPILOT_TRANSPORT=tcp` 时绑 `127.0.0.1:0`。
- [X] T2 daemon：写 `{transport,host,port,pid,token}` 到原 socket 路径；每条请求校验 token。
- [X] T3 client：`endpoint()` 判别传输方式，TCP 连接带 token。
- [X] T4 client：残留描述文件按 pid 探活后清理。
- [X] V1 Linux 强制 tcp：`ping` 0.15s 成功，描述文件字段正确。
- [X] V2 无 token 连接被拒；带 token 通过。
- [ ] V3 真实 Windows 回测（无 AF_UNIX 分支、杀 daemon 后自愈）。
