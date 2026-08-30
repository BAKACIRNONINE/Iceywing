#!/usr/bin/env sh
set -eu

echo "* Iceywing bootstrap"
echo ""

if ! command -v python3 >/dev/null 2>&1; then
  echo "[FAIL] Python 3.11+ is required."
  exit 1
fi

echo "[....] Installing Iceywing..."
python3 -m pip install .
echo "[OK] Iceywing"

if command -v just >/dev/null 2>&1; then
  echo "[OK] just"
else
  echo "[WARN] just is not installed. Install it with your system package manager."
fi

echo ""
echo "[OK] Installation complete"
echo "Try: iceywing --help"
