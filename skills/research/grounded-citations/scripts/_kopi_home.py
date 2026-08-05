"""Resolve KOPI_HOME for standalone skill scripts.

Skill scripts may run outside the Kopi process (system Python, nix env,
CI) where ``kopi_constants`` is not importable.  This module provides the
same ``get_kopi_home()`` contract without requiring it on ``sys.path``.

When ``kopi_constants`` IS available it is used directly so profile
resolution and any future enhancements are picked up automatically.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from kopi_constants import get_kopi_home as get_kopi_home
except (ModuleNotFoundError, ImportError):

    def get_kopi_home() -> Path:
        """Return the Kopi home directory (default: ``~/.kopi``)."""
        val = os.environ.get("KOPI_HOME", "").strip()
        return Path(val) if val else Path.home() / ".kopi"
