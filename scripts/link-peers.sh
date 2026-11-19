#!/usr/bin/env bash
# 把插件需要的 DSH peer 依赖软链到仓库 node_modules，供 `dsh plugin add <目录>`（link: 安装）使用。
#
# 背景：本地目录安装时插件是软链，Node 从仓库真实路径解析 `@deepseek-ai/dsh-tools` 等
# 会失败（这些包随 dsh 运行时分发，不在 npm 公共仓库）。软链指向运行时的同一份代码，
# 保证 cordis 仍是单实例。
#
# 用法：scripts/link-peers.sh            # 自动从 dsh 启动器推断运行时目录
#       DSH_RUNTIME=/path/to/runtime scripts/link-peers.sh
set -euo pipefail

here=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
runtime="${DSH_RUNTIME:-}"

if [ -z "$runtime" ]; then
  shim=$(command -v dsh || true)
  if [ -n "$shim" ] && [ -f "$shim" ]; then
    runtime=$(sed -n 's#.*[[:space:]]\(/[^ ]*\)/node_modules/@deepseek-ai/dsh/lib/bin\.js.*#\1#p' "$shim" | head -1)
  fi
fi

if [ -z "$runtime" ] || [ ! -d "$runtime/node_modules/@deepseek-ai" ]; then
  echo "未能确定 DSH 运行时目录；请设置 DSH_RUNTIME=<含 node_modules/@deepseek-ai 的目录>" >&2
  exit 1
fi

mkdir -p "$here/node_modules/@deepseek-ai"
for pkg in dsh-tools schemastery cordis; do
  src="$runtime/node_modules/@deepseek-ai/$pkg"
  if [ ! -d "$src" ]; then
    echo "缺少 $src" >&2
    exit 1
  fi
  ln -sfn "$src" "$here/node_modules/@deepseek-ai/$pkg"
  echo "linked $pkg -> $src"
done
echo "完成：插件目录 $(basename "$here") 现在可以解析 DSH peer 依赖"
