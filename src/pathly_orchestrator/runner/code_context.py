"""Code-structure context provider for agent prompts (shared B/C backend).

`build_block(scope, files, role, budget)` returns an advisory
``## Code structure`` markdown block describing the blast-radius / callers /
call-chain for the in-scope files, sourced from a pluggable code-intelligence
backend (``none | cli | ...``). It is the single foundation consumed by both
surfaces of the code-intelligence initiative:

* **B-inject** — the supervisor pre-injects this block into runner-mode prompts.
* **C (code-intel-proxy)** — the ``POST /code/query`` route serves it on demand.

Contract (mirrors :func:`comms_context.retrieve_board_context`): this module
**never raises** and returns ``""`` on any failure or when no backend is
configured, so it can never break prompt assembly — the "never break the
prompt" idiom (F9 in the context-retrieval spec).

Phase 1 (this commit) ships the interface + the ``none`` no-op backend (the
default, safe-off). Later phases extend it *by adding*, not by rewriting:

* Phase 2 — register a ``cli`` backend (shells out to gitnexus).
* Phase 3 — content-hash caching keyed by ``(path, content-hash)``.
* Phase 4 — :func:`_resolve_backend` reads ``code_context.backend`` from the
  ``~/.pathly`` config instead of the hard-coded ``"none"`` below.
"""

from __future__ import annotations

import logging
from typing import Protocol, Sequence, runtime_checkable

logger = logging.getLogger(__name__)

# Default char budget for the injected block (chars, a conservative ~tokens*4
# upper bound). Callers may pass a tighter budget per role/phase.
_DEFAULT_BUDGET = 1500


@runtime_checkable
class CodeContextProvider(Protocol):
    """A pluggable code-intelligence backend.

    An implementation turns "these files are in scope" into an advisory
    markdown block (blast radius / callers / call chain), or ``""`` when it has
    nothing to add. Implementations **must never raise** — any internal failure
    (missing binary, missing index, query error) degrades to ``""`` so the
    caller falls back to plain Grep/Read.
    """

    #: Short backend identifier, surfaced to callers (e.g. in the ``backend``
    #: field of the proxy response). One of ``none | cli | mcp``.
    name: str

    def build_block(
        self,
        scope: str,
        files: Sequence[str],
        role: str,
        budget: int,
    ) -> str:
        """Return an advisory block for ``files``, or ``""`` when empty."""
        ...


class NoneProvider:
    """Default backend: always returns ``""`` (code context disabled / safe-off).

    Pathly ships with this backend active so the feature is a guaranteed no-op
    until the user opts in (Phase 4 config switch). It exists as a real provider
    — rather than a ``None`` sentinel — so :func:`build_block` has a uniform
    call path and no special-casing.
    """

    name = "none"

    def build_block(
        self,
        scope: str,
        files: Sequence[str],
        role: str,
        budget: int,
    ) -> str:
        # Intentionally ignores every argument — the safe-off backend.
        del scope, files, role, budget
        return ""


# Backend registry. Open/closed: Phase 2 adds ``"cli"`` (and later ``"mcp"``)
# here without touching build_block(). Keys are the values of the
# ``code_context.backend`` setting (``off`` maps to ``none``).
_PROVIDERS: dict[str, CodeContextProvider] = {
    "none": NoneProvider(),
}


def get_provider(backend: str | None) -> CodeContextProvider:
    """Return the provider for ``backend``, falling back to the ``none`` no-op.

    An unknown or ``None`` backend resolves to :class:`NoneProvider`, so a bad
    or stale config value can never raise — it just disables the feature.
    ``"off"`` is treated as an alias for ``"none"`` (the config uses ``off``).
    """
    key = (backend or "none").strip().lower()
    if key == "off":
        key = "none"
    return _PROVIDERS.get(key, _PROVIDERS["none"])


def _resolve_backend() -> str:
    """Return the configured backend name.

    Phase 1: always ``"none"`` (safe-off). Phase 4 wires this to the
    ``code_context.backend`` setting in the ``~/.pathly`` config. Kept as a
    separate seam so :func:`build_block`'s public signature stays stable across
    phases.
    """
    return "none"


def build_block(
    scope: str,
    files: Sequence[str],
    role: str,
    budget: int = _DEFAULT_BUDGET,
) -> str:
    """Return an advisory ``## Code structure`` block for ``files``, or ``""``.

    Parameters
    ----------
    scope:
        The feature / goal scope key the task belongs to (used by real backends
        for caching and logging; ignored by the ``none`` backend).
    files:
        The files in scope for the upcoming agent task. ``None`` is tolerated
        and treated as "no files".
    role:
        The role of the agent that will receive the block (e.g. ``builder``),
        so a backend can tier the depth of structural detail per role.
    budget:
        Soft char budget for the rendered block.

    Notes
    -----
    **Never raises.** Any failure returns ``""`` (the "never break the prompt"
    idiom). Phase 1 always returns ``""`` because :func:`_resolve_backend`
    yields ``"none"``.
    """
    try:
        provider = get_provider(_resolve_backend())
        return provider.build_block(
            scope,
            list(files or []),
            role or "",
            int(budget),
        )
    except Exception:
        logger.debug(
            "code_context: build_block failed — returning empty block",
            exc_info=True,
        )
        return ""
