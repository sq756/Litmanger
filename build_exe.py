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
    cmd = [sys.executable, "-m", "PyInstaller", "--onefile", "--name", "Litmanger", "--clean"]
    if IS_WIN:
        cmd.append("--noconsole")
        cmd += ["--add-data", "index.html;."]
    else:
        cmd += ["--add-data", "index.html:."]
    cmd += [
        "--hidden-import", "cryptography",
        "--hidden-import", "cryptography.hazmat.primitives.asymmetric.ed25519",
        "--hidden-import", "cryptography.hazmat.primitives.serialization",
        "server.py",
    ]
    print(f"[BUILD] Running: {' '.join(cmd)}")
    subprocess.check_call(cmd)

    out_dir = DIST

    # PyInstaller --onefile puts the exe directly in dist/
    exe = out_dir / ("Litmanger.exe" if IS_WIN else "Litmanger")
    if exe.exists():
        size_mb = exe.stat().st_size / (1024 * 1024)
        print(f"[BUILD] Done: {exe} ({size_mb:.1f} MB)")
    else:
        candidates = list(out_dir.glob("Litmanger*"))
        print(f"[BUILD] Output files: {[c.name for c in candidates]}")


if __name__ == "__main__":
    clean()
    build()
