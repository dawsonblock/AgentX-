#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "[1/4] Ensuring dependencies are installed"
if [[ ! -d node_modules ]]; then
  volta run npm install
fi

echo "[2/4] Building workspace"
volta run npm run build

echo "[3/4] Installing current checkout globally"
volta run npm install -g .

echo "[4/4] Verifying CLI from this install"
volta run gsd --version
volta run gsd --help | sed -n '1,20p'

echo
echo "Done. If your shell still cannot find 'gsd', run:"
echo "  source ~/.bashrc   # or restart shell"
