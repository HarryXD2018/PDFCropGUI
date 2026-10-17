#!/usr/bin/env bash
# macOS / Linux launcher. Creates the conda env on first run, then starts the GUI.
set -euo pipefail
cd "$(dirname "$0")"

ENV_NAME="${PDFCROPGUI_ENV:-pdfcropgui}"
PY_VERSION="3.11"
PIP_INDEX="${PDFCROPGUI_PIP_INDEX:-https://pypi.corp.kuaishou.com/kuaishou/prod}"
PIP_HOST="$(printf '%s' "$PIP_INDEX" | sed -E 's#^[a-z]+://([^/]+).*#\1#')"

if ! command -v conda >/dev/null 2>&1; then
  echo "conda not found. Install Miniconda or Anaconda first." >&2
  exit 1
fi

CONDA_BASE="$(conda info --base)"
ENV_PREFIX="$CONDA_BASE/envs/$ENV_NAME"
PYTHON="$ENV_PREFIX/bin/python"
DEPS_MARKER="$ENV_PREFIX/.pdfcrop-gui-1.3.0"

if [ ! -x "$PYTHON" ]; then
  echo "Creating conda env '$ENV_NAME' (Python $PY_VERSION)..."
  conda create -y -n "$ENV_NAME" "python=$PY_VERSION" tk
fi

if [ ! -f "$DEPS_MARKER" ]; then
  echo "Installing dependencies from $PIP_INDEX ..."
  "$PYTHON" -m pip install --upgrade pip -i "$PIP_INDEX" --trusted-host "$PIP_HOST"
  "$PYTHON" -m pip install -r requirements.txt -i "$PIP_INDEX" --trusted-host "$PIP_HOST"
  echo ready >"$DEPS_MARKER"
fi

exec "$PYTHON" main.py "$@"
