#!/usr/bin/env sh
set -eu

EXPECTED_VERSION="0.4.0"

echo "* Iceywing Setup"
echo ""

if ! command -v python3 >/dev/null 2>&1; then
  echo "[FAIL] Python 3.11+ is required."
  exit 1
fi

echo "[OK] Check Python $(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')"

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
WHEEL=$(find "$SCRIPT_DIR/dist" -maxdepth 1 -type f -name "iceywing-${EXPECTED_VERSION}-*.whl" -print 2>/dev/null | head -n 1 || true)
if [ -z "$WHEEL" ]; then
  echo "[FAIL] Install / upgrade"
  echo "Installer wheel for Iceywing $EXPECTED_VERSION was not found."
  echo "Extract the release ZIP into a clean folder and try again."
  exit 1
fi

if python3 -m pip install --upgrade "$WHEEL"; then
  echo "[OK] Install / upgrade"
else
  echo "[FAIL] Install / upgrade"
  exit 1
fi

if python3 -c "import iceywing; raise SystemExit(0 if iceywing.__version__ == '$EXPECTED_VERSION' else 1)"; then
  echo "[OK] Verify"
else
  echo "[FAIL] Verify"
  exit 1
fi

echo ""
echo "[OK] Iceywing $EXPECTED_VERSION ready"
echo "Try: iceywing --help"
