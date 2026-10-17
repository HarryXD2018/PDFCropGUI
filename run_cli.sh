#!/usr/bin/env bash
# Command-line automatic crop.
# Usage: ./run_cli.sh <file.pdf> [extra autocrop.py options]
# Defaults: 2 mm padding on all four sides, output kept beside the input
# as <name>_cropped.pdf.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ "$#" -lt 1 ]; then
  echo "用法: $0 <file.pdf> [更多 autocrop.py 参数]" >&2
  echo "示例: $0 文档.pdf            # 生成 文档_cropped.pdf，四边留 2mm" >&2
  exit 2
fi

ENV_NAME="${PDFCROPGUI_ENV:-pdfcropgui}"
PY_VERSION="3.11"
PIP_INDEX="${PDFCROPGUI_PIP_INDEX:-https://pypi.corp.kuaishou.com/kuaishou/prod}"
PIP_HOST="$(printf '%s' "$PIP_INDEX" | sed -E 's#^[a-z]+://([^/]+).*#\1#')"

if ! command -v conda >/dev/null 2>&1; then
  echo "未找到 conda，请先安装 Miniconda 或 Anaconda。" >&2
  exit 1
fi

CONDA_BASE="$(conda info --base)"
ENV_PREFIX="$CONDA_BASE/envs/$ENV_NAME"
PYTHON="$ENV_PREFIX/bin/python"
DEPS_MARKER="$ENV_PREFIX/.pdfcrop-gui-1.3.0"

if [ ! -x "$PYTHON" ]; then
  echo "正在创建 conda 环境 '$ENV_NAME'（Python $PY_VERSION）..."
  conda create -y -n "$ENV_NAME" "python=$PY_VERSION" tk
fi

if [ ! -f "$DEPS_MARKER" ]; then
  echo "正在从 $PIP_INDEX 安装依赖 ..."
  "$PYTHON" -m pip install --upgrade pip -i "$PIP_INDEX" --trusted-host "$PIP_HOST"
  "$PYTHON" -m pip install -r "$SCRIPT_DIR/requirements.txt" -i "$PIP_INDEX" --trusted-host "$PIP_HOST"
  echo ready >"$DEPS_MARKER"
fi

# Keep the caller's working directory so relative PDF paths resolve normally;
# the project root only needs to be importable.
export PYTHONPATH="$SCRIPT_DIR${PYTHONPATH:+:$PYTHONPATH}"
exec "$PYTHON" "$SCRIPT_DIR/autocrop.py" "$@"
