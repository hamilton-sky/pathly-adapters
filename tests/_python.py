"""A command that runs Python code in THIS interpreter, for check blocks and verify settings.

A bare ``python`` is not on every PATH (macOS ships only ``python3``; a venv may not be
activated), so a test whose check block said ``$ python -c …`` failed for a reason that had
nothing to do with what it tests. ``proof/command.py::to_argv`` reads a command that starts
with ``[`` as a JSON argv, so ``sys.executable`` goes through untouched on every platform
(no shell quoting of a path with spaces or backslashes).
"""

from __future__ import annotations

import json
import sys


def python_command(code: str) -> str:
    """``code`` run by ``sys.executable -c``, as a JSON argv string."""
    return json.dumps([sys.executable, "-c", code])
