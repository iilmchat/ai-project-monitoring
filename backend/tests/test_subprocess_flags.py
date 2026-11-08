"""Windows no-console flags for child processes (S48-Fix)."""

from __future__ import annotations

import os

from app.core.subprocess_flags import CREATE_NO_WINDOW, WINDOWS_CREATION_FLAGS


def test_create_no_window_value() -> None:
    assert CREATE_NO_WINDOW == 0x08000000


def test_creation_flags_only_on_windows() -> None:
    if os.name == "nt":
        assert WINDOWS_CREATION_FLAGS == CREATE_NO_WINDOW
    else:
        assert WINDOWS_CREATION_FLAGS == 0
