#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"

show_help() {
    echo "Litmanger — Academic Paper Manager"
    echo ""
    echo "  ./run.sh <URL>      Add a paper"
    echo "  ./run.sh server     Start dashboard"
    echo "  ./run.sh list       List all papers"
    echo "  ./run.sh html       Generate static HTML"
    echo "  ./run.sh watch      Watch Downloads for PDFs"
}

case "${1:-}" in
    server)
        python -m litmanger server
        ;;
    list|--list)
        python -m litmanger --list
        ;;
    html|--html)
        python -m litmanger --html
        ;;
    watch)
        echo "Watching Downloads folder..."
        powershell -ExecutionPolicy Bypass -File "$ROOT/watch_downloads.ps1"
        ;;
    ""|--help|-h)
        show_help
        ;;
    *)
        python -m litmanger "$1"
        ;;
esac
