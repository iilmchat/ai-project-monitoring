"""Platform-specific subprocess flags.

The Tauri desktop sidecar is a windowed PyInstaller executable. On Windows any
console child process (git, pip, pnpm, ...) launched without ``CREATE_NO_WINDOW``
can briefly allocate its own console window, which looks like a black flashing
window. Apply these flags to every external command.
"""

from __future__ import annotations

import os

CREATE_NO_WINDOW = 0x08000000

# ``creationflags`` is accepted by subprocess on every platform; zero means
# "default" on POSIX.
WINDOWS_CREATION_FLAGS: int = CREATE_NO_WINDOW if os.name == "nt" else 0

__all__ = ["CREATE_NO_WINDOW", "WINDOWS_CREATION_FLAGS"]
