"""Build the PyInstaller sidecar consumed by Tauri (S48-001).

Usage (from ``backend/``):
    pip install -r requirements-desktop.txt
    python build_sidecar.py
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path


def target_triple() -> str:
    machine = platform.machine().lower()
    if sys.platform == "win32":
        return (
            "aarch64-pc-windows-msvc"
            if machine in {"arm64", "aarch64"}
            else "x86_64-pc-windows-msvc"
        )
    if sys.platform == "darwin":
        return (
            "aarch64-apple-darwin"
            if machine in {"arm64", "aarch64"}
            else "x86_64-apple-darwin"
        )
    return (
        "aarch64-unknown-linux-gnu"
        if machine in {"arm64", "aarch64"}
        else "x86_64-unknown-linux-gnu"
    )


def main() -> int:
    backend = Path(__file__).resolve().parent
    frontend = backend.parent / "frontend"
    output_dir = frontend / "src-tauri" / "binaries"
    build_dir = backend / "build" / "sidecar"
    output_dir.mkdir(parents=True, exist_ok=True)
    build_dir.mkdir(parents=True, exist_ok=True)

    name = "iiruchating-backend"
    args = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name",
        name,
        "--distpath",
        str(output_dir),
        "--workpath",
        str(build_dir / "work"),
        "--specpath",
        str(build_dir),
        "--collect-all",
        "pygit2",
        "--collect-all",
        "bcrypt",
        "--collect-all",
        "certifi",
        "--collect-submodules",
        "app",
        "--hidden-import",
        "app.main",
        "--hidden-import",
        "aiosqlite",
        "--hidden-import",
        "sqlalchemy.dialects.sqlite.aiosqlite",
        "--hidden-import",
        "uvicorn.logging",
        "--hidden-import",
        "uvicorn.loops.auto",
        "--hidden-import",
        "uvicorn.protocols.http.auto",
        "--hidden-import",
        "uvicorn.protocols.websockets.auto",
        "--hidden-import",
        "uvicorn.lifespan.on",
        "--exclude-module",
        "tkinter",
        str(backend / "sidecar_entry.py"),
    ]
    if sys.platform == "win32":
        args.insert(4, "--noconsole")
    else:
        args.insert(4, "--windowed")

    subprocess.run(args, cwd=backend, check=True)

    suffix = ".exe" if sys.platform == "win32" else ""
    built = output_dir / f"{name}{suffix}"
    target = output_dir / f"{name}-{target_triple()}{suffix}"
    if not built.exists():
        print(f"PyInstaller output not found: {built}", file=sys.stderr)
        return 1
    shutil.copy2(built, target)
    print(f"Sidecar: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
