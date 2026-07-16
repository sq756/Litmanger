#!/usr/bin/env bash
# Litmanger launcher — auto-detects Python and starts the dashboard
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

# Find Python
PYTHON=""
for cmd in python3 python py; do
    if command -v "$cmd" &>/dev/null; then
        PYTHON="$cmd"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "[ERROR] Python not found. Install Python 3.9+:"
    echo "  macOS:   brew install python3"
    echo "  Linux:   sudo apt install python3  (or your package manager)"
    echo "  Windows: https://www.python.org/downloads/"
    exit 1
fi

echo "Litmanger — starting..."
echo ""
$PYTHON server.py
