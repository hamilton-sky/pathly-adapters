"""The values of ``comms_messages.author_source`` and the ``system`` stamp, defined once.

``db/`` imports nothing internal, so ``runner/provenance.py`` (the stamp functions), the
query modules that write ``system`` rows themselves, and ``post_message`` (which rejects an
unknown source) all import from here.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

SOURCE_TOKEN = "token"  # the caller's run token named a run and a role
SOURCE_SYSTEM = "system"  # a row the server composed itself
SOURCE_LEGACY = "legacy"  # a row written before provenance existed (backfilled)
SOURCE_NONE = "none"  # unverified: no token, or one that names no role

AUTHOR_SOURCES = frozenset({SOURCE_TOKEN, SOURCE_SYSTEM, SOURCE_LEGACY, SOURCE_NONE})

SYSTEM_ROLE = "system"

# The three author columns of a server-written row, ready to pass as ``**SYSTEM_AUTHOR``.
SYSTEM_AUTHOR: Mapping[str, Any] = MappingProxyType(
    {"author_role": SYSTEM_ROLE, "author_run_id": None, "author_source": SOURCE_SYSTEM}
)

# (author_role, author_source) of a server-written row, for positional SQL parameters.
SYSTEM_PAIR = (SYSTEM_ROLE, SOURCE_SYSTEM)
