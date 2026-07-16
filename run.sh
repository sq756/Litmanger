#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"

# Find Python
PYTHON=""
for cmd in python3 python py; do
    if command -v "$cmd" &>/dev/null; then
        PYTHON="$cmd"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "[ERROR] Python not found. Install Python 3.9+ from https://www.python.org/downloads/"
    exit 1
fi

show_help() {
    echo "Litmanger — Academic Paper Manager"
    echo ""
    echo "  ./run.sh <URL>      Add a paper"
    echo "  ./run.sh server     Start dashboard → http://127.0.0.1:8765"
    echo "  ./run.sh list       List all papers"
    echo "  ./run.sh html       Generate static HTML"
    echo "  ./run.sh watch      Watch Downloads folder for PDFs"
}

case "${1:-}" in
    server)
        $PYTHON -m litmanger server
        ;;
    list|ls)
        $PYTHON -m litmanger list
        ;;
    html)
        $PYTHON -m litmanger html
        ;;
    watch)
        echo "Watching Downloads folder..."
        powershell -ExecutionPolicy Bypass -File "$ROOT/watch_downloads.ps1"
        ;;
    ""|--help|-h)
        show_help
        ;;
    *)
        $PYTHON -m litmanger "$1"
        ;;
esac
