"""Code-structure context provider for agent prompts (shared B/C backend).

`build_block(scope, files, role, budget)` returns an advisory
``## Code structure`` markdown block for the in-scope files, sourced from a
pluggable backend (``none`` | ``cli``). Consumed by both surfaces of the
code-intelligence initiative:

* **B-inject** — the supervisor pre-injects this block into runner-mode prompts.
* **C (code-intel-proxy)** — the ``POST /code/query`` route serves it on demand.

Contract (mirrors :func:`comms_context.retrieve_board_context`): this module
**never raises** and returns ``""`` on any failure or when no backend is
configured, so it can never break prompt assembly.

This file owns the interface, config, and dispatch; the concrete ``cli`` backend
(codebase-memory-mcp) lives in :mod:`.code_context_cli`.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from typing import Protocol, Sequence, runtime_checkable

from .code_context_cli import CliProvider

logger = logging.getLogger(__name__)

# Default char budget for the injected block (chars, a conservative ~tokens*4
# upper bound). Callers may pass a tighter budget per role/phase.
_DEFAULT_BUDGET = 1500


@runtime_checkable
class CodeContextProvider(Protocol):
    """A pluggable code-intelligence backend.

    An implementation turns "these files are in scope" into an advisory markdown
    block (callers / callees / structure), or ``""`` when it has nothing to add.
    Implementations **must never raise** — any internal failure degrades to
    ``""`` so the caller falls back to plain Grep/Read.
    """

    #: Short backend identifier surfaced to callers (e.g. the ``backend`` field
    #: of the proxy response). One of ``none | cli``.
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
    until the user opts in via the config switch. It exists as a real provider —
    rather than a ``None`` sentinel — so :func:`build_block` has a uniform call
    path and no special-casing.
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


# Static backend registry. ``none`` is a singleton; the ``cli`` backend is built
# on demand in :func:`get_provider` because it is parameterised by the
# ``code_context.tool`` setting. ``off`` maps to ``none``.
_PROVIDERS: dict[str, CodeContextProvider] = {
    "none": NoneProvider(),
}


def get_provider(backend: str | None) -> CodeContextProvider:
    """Return the provider for ``backend``, falling back to the ``none`` no-op.

    ``off`` / unknown / ``None`` resolve to :class:`NoneProvider` (safe-off).
    ``cli`` resolves to a :class:`CliProvider` configured with the current
    ``code_context.tool`` setting. A bad or stale value can never raise.
    """
    key = (backend or "none").strip().lower()
    if key == "off":
        key = "none"
    if key == "cli":
        return CliProvider(_resolve_tool())
    return _PROVIDERS.get(key, _PROVIDERS["none"])


def _get_setting(key: str, default: str) -> str:
    """Read a string setting from the central ``~/.pathly`` config (app_settings).

    Never raises — any DB/import failure returns ``default``, so a config lookup
    can never break prompt assembly. (``runner -> db`` is an allowed downward
    import.)
    """
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.app_settings import get_setting

        val = get_setting(get_db(), key, default)
        return val if isinstance(val, str) and val.strip() else default
    except Exception:
        logger.debug("code_context: setting %r lookup failed", key, exc_info=True)
        return default


def _resolve_backend() -> str:
    """Return the active backend from the ``code_context.backend`` setting.

    Values: ``off`` (default, safe-off → ``none``) or ``cli``. Persisted in
    ``~/.pathly`` via app_settings and read at call time, so flipping it takes
    effect without a server restart.
    """
    key = _get_setting("code_context.backend", "off").strip().lower()
    return "cli" if key == "cli" else "none"


def _resolve_tool() -> str:
    """Return the ``code_context.tool`` setting — the cli backend's binary name.

    Defaults to ``codebase-memory-mcp`` (the cross-platform graph engine that
    replaced gitnexus); ``gitnexus`` stays available (e.g. Linux/CI). An
    unrecognised value falls back to the default.
    """
    key = _get_setting("code_context.tool", "codebase-memory-mcp").strip().lower()
    return key if key in ("codebase-memory-mcp", "gitnexus") else "codebase-memory-mcp"


def _resolve_reindex() -> str:
    """Return the ``code_context.reindex`` setting: ``off | stage | auto``.

    Defaults to ``auto``. ``stage`` = Pathly re-indexes at each stage boundary;
    ``auto`` = let the tool self-index (``auto_index``); ``off`` = never.
    """
    key = _get_setting("code_context.reindex", "auto").strip().lower()
    return key if key in ("off", "stage", "auto") else "auto"


_auto_index_done = False


def maybe_reindex(project_root: str) -> None:
    """Freshness bridge — fire-and-forget re-index per ``code_context.reindex``.

    Called once per stage from runner prompt assembly. Only acts for the
    cli/codebase-memory-mcp backend; **never raises, never blocks** (runs in a
    daemon thread). ``stage`` → ``index_repository`` (incremental: persisted
    hashes mean only changed files are re-processed); ``auto`` → set the tool's
    own ``auto_index`` once; ``off`` → nothing.
    """
    global _auto_index_done
    try:
        if _resolve_backend() != "cli" or _resolve_reindex() == "off":
            return
        if _resolve_tool() != "codebase-memory-mcp":
            return
        exe = shutil.which("codebase-memory-mcp")
        if not exe:
            return
        if _resolve_reindex() == "auto":
            if _auto_index_done:
                return
            _auto_index_done = True
            argv = [exe, "config", "set", "auto_index", "true"]
        else:  # stage
            root = os.path.abspath(project_root or os.getcwd()).replace("\\", "/")
            argv = [exe, "cli", "index_repository", json.dumps({"repo_path": root})]

        def _bg() -> None:
            try:
                subprocess.run(argv, capture_output=True, text=True, timeout=180)
            except Exception:
                pass

        import threading

        threading.Thread(target=_bg, daemon=True).start()
    except Exception:
        logger.debug("code_context: maybe_reindex failed", exc_info=True)


def build_block(
    scope: str,
    files: Sequence[str],
    role: str,
    budget: int = _DEFAULT_BUDGET,
) -> str:
    """Return an advisory ``## Code structure`` block for ``files``, or ``""``.

    **Never raises.** Any failure returns ``""`` (the "never break the prompt"
    idiom); the default backend is ``none`` (safe-off).
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
