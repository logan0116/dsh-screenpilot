# Feature Specification: Windows 文档与解释器探测

**Feature Branch**: `019-windows-docs`

**Created**: 2026-11-19

**Status**: Draft

**Input**: 需求 019-AR（同事反馈第5/9条）。

## Requirements（草案）

- **FR-001**: `defaultPython()` 探测补 Windows venv 路径 `.venv/Scripts/python.exe`。
- **FR-002**: README 补 Windows 支持状态、`pythonBin` 示例（`<venv>\\Scripts\\python.exe`）。
- **FR-003**: README 补首调耗时预期与编码说明（采纳 BUG-03 后可一句"已内置 UTF-8"）。
- **FR-004**: 说明 `py` launcher 在 uv 管理环境下的坑。

## 验证计划

- Linux 上 `.venv/bin/python` 探测不回归；
- 文档条目逐条对照同事反馈的 9 条。

## 实现与验证（2026-11-20）

- `defaultPython()` 探测列表补 Windows venv：`.venv/Scripts/python.exe`。
- README 新增 Windows 小节（传输层回退与 token、`pythonBin` 绝对路径示例、
  内置 UTF-8、首调耗时预期）。
- 验证：Linux 上探测仍命中 `.venv/bin/python`（`Config({}).pythonBin` 输出确认）。
