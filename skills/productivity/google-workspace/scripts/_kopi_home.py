"""Resolve KOPI_HOME for standalone skill scripts.

Skill scripts may run outside the Kopi process (e.g. system Python,
nix env, CI) where ``kopi_constants`` is not importable.  This module
provides the same ``get_kopi_home()`` and ``display_kopi_home()``
contracts as ``kopi_constants`` without requiring it on ``sys.path``.

When ``kopi_constants`` IS available it is used directly so that any
future enhancements (profile resolution, Docker detection, etc.) are
picked up automatically.  The fallback path replicates the core logic
from ``kopi_constants.py`` using only the stdlib.

All scripts under ``google-workspace/scripts/`` should import from here
instead of duplicating the ``KOPI_HOME = Path(os.getenv(...))`` pattern.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from kopi_constants import display_kopi_home as display_kopi_home
    from kopi_constants import get_kopi_home as get_kopi_home
except (ModuleNotFoundError, ImportError):

    def get_kopi_home() -> Path:
        """Return the Kopi home directory (default: ~/.kopi).

        Mirrors ``kopi_constants.get_kopi_home()``."""
        val = os.environ.get("KOPI_HOME", "").strip()
        return Path(val) if val else Path.home() / ".kopi"

    def display_kopi_home() -> str:
        """Return a user-friendly ``~/``-shortened display string.

        Mirrors ``kopi_constants.display_kopi_home()``."""
        home = get_kopi_home()
        try:
            return "~/" + str(home.relative_to(Path.home()))
        except ValueError:
            return str(home)
