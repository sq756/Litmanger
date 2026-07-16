"""
PyInstaller build script for Litmanger standalone.
Works on Windows, macOS, and Linux.
"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
DIST = ROOT / "dist"
BUILD = ROOT / "build"
IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"


def clean():
    for d in (DIST, BUILD):
        try:
            if d.exists():
                shutil.rmtree(d, ignore_errors=True)
        except Exception:
            pass  # CI sometimes has permission issues, ignore
    for spec in ROOT.glob("*.spec"):
        try:
            spec.unlink()
        except Exception:
            pass


def build():
    cmd = [sys.executable, "-m", "PyInstaller", "--onedir", "--name", "Litmanger", "--clean"]
    if IS_WIN:
        cmd.append("--noconsole")
    cmd += [
        "--hidden-import", "cryptography",
        "--hidden-import", "cryptography.hazmat.primitives.asymmetric.ed25519",
        "--hidden-import", "cryptography.hazmat.primitives.serialization",
        "server.py",
    ]
    print(f"[BUILD] Running: {' '.join(cmd)}")
    subprocess.check_call(cmd)

    out_dir = DIST / "Litmanger"

    # Copy data files
    for f in ("index.html", "papers.json", "config.json"):
        src = ROOT / f
        if src.exists():
            shutil.copy2(src, out_dir / f)
            print(f"[BUILD] Copied {f}")

    # Empty pdfs dir
    (out_dir / "pdfs").mkdir(exist_ok=True)

    # Platform launcher
    if IS_WIN:
        launcher = out_dir / "start.bat"
        launcher.write_text(
            '@echo off\r\ncd /d "%~dp0"\r\nif not exist "pdfs" mkdir "pdfs"\r\nstart "" /B "Litmanger.exe"\r\n',
            encoding="ascii",
        )
    else:
        launcher = out_dir / "Litmanger"
        exe_name = "Litmanger" + (".exe" if IS_WIN else "")
        launch_script = out_dir / "start.sh"
        launch_script.write_text(f'#!/bin/sh\ncd "$(dirname "$0")"\nmkdir -p pdfs\n./Litmanger &\n', encoding="ascii")
        launch_script.chmod(0o755)

    # Verify output
    exe = out_dir / ("Litmanger.exe" if IS_WIN else "Litmanger")
    if exe.exists():
        size_mb = exe.stat().st_size / (1024 * 1024)
        print(f"[BUILD] Done: {exe} ({size_mb:.1f} MB)")
    else:
        # On Windows PyInstaller puts exe at root, on Linux/Mac in _internal or as standalone
        candidates = list(out_dir.glob("Litmanger*"))
        print(f"[BUILD] Output files: {[c.name for c in candidates]}")


if __name__ == "__main__":
    clean()
    build()
