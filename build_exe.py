"""
PyInstaller build script for Litmanger standalone exe.

Run: python build_exe.py
Output: dist/Litmanger/  (copy this folder anywhere)
"""
import subprocess
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
DIST = ROOT / "dist"
BUILD = ROOT / "build"


def clean():
    for d in (DIST, BUILD):
        if d.exists():
            shutil.rmtree(d)
    spec = ROOT / "Litmanger.spec"
    if spec.exists():
        spec.unlink()


def build():
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onedir",
        "--name", "Litmanger",
        "--clean",
        "--noconsole",
        "server.py",
    ]
    subprocess.check_call(cmd)

    # Copy data files alongside the exe (they go in _internal/, not where we need them)
    for f in ("index.html", "papers.json", "config.json"):
        shutil.copy2(ROOT / f, DIST / "Litmanger" / f)

    # Create empty pdfs dir
    pdfs_dir = DIST / "Litmanger" / "pdfs"
    pdfs_dir.mkdir(exist_ok=True)

    # Convenience launcher (exe auto-opens browser on its own)
    launcher = DIST / "Litmanger" / "start.bat"
    launcher.write_text(
        '@echo off\r\n'
        'cd /d "%~dp0"\r\n'
        'if not exist "pdfs" mkdir "pdfs"\r\n'
        'start "" /B "Litmanger.exe"\r\n',
        encoding="ascii",
    )

    print("\nDone! Output:", DIST / "Litmanger")
    print("Copy the entire Litmanger folder anywhere. Double-click start.bat.")


if __name__ == "__main__":
    clean()
    build()
