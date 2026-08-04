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
import time
from typing import Protocol, Sequence, runtime_checkable

from .code_context_cli import CliProvider
from .code_context_lsp import LspProvider

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
        project_root: str = "",
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
        project_root: str = "",
    ) -> str:
        # Intentionally ignores every argument — the safe-off backend.
        del scope, files, role, budget, project_root
        return ""


class CompositeProvider:
    """Runs several backends and concatenates their non-empty blocks.

    Backs the ``both`` engine: the graph (``cli``) gives breadth and the LSP
    (``lsp``) gives always-fresh precision, so one ``/code/query`` returns both
    under a single response. Never raises — a failing child simply contributes
    nothing; the joined block is truncated to ``budget``.
    """

    name = "both"

    def __init__(self, providers: Sequence[CodeContextProvider]) -> None:
        self._providers = list(providers)

    def build_block(
        self,
        scope: str,
        files: Sequence[str],
        role: str,
        budget: int,
        project_root: str = "",
    ) -> str:
        blocks: list[str] = []
        for p in self._providers:
            try:
                b = p.build_block(scope, files, role, budget, project_root)
            except Exception:
                b = ""
            if b:
                blocks.append(b)
        return "\n\n".join(blocks)[: max(0, int(budget))]


# Static backend registry. ``none`` is a singleton; the ``cli`` backend is built
# on demand in :func:`get_provider` because it is parameterised by the
# ``code_context.tool`` setting. ``off`` maps to ``none``.
_PROVIDERS: dict[str, CodeContextProvider] = {
    "none": NoneProvider(),
}


def get_provider(backend: str | None) -> CodeContextProvider:
    """Return the provider for ``backend``, falling back to the ``none`` no-op.

    ``off`` / unknown / ``None`` resolve to :class:`NoneProvider` (safe-off).
    ``cli`` → :class:`CliProvider` (codebase-memory-mcp graph). ``lsp`` →
    :class:`LspProvider` (Serena, always-fresh). ``both`` → a
    :class:`CompositeProvider` of graph + lsp. A bad or stale value can never
    raise.
    """
    key = (backend or "none").strip().lower()
    if key == "off":
        key = "none"
    if key == "cli":
        return CliProvider(_resolve_tool())
    if key == "lsp":
        return LspProvider()
    if key == "both":
        return CompositeProvider([CliProvider(_resolve_tool()), LspProvider()])
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

    Values: ``auto`` (**default** — detect an installed backend, see
    :func:`_auto_backend`), ``off`` (safe-off → ``none``), ``cli`` (graph), ``lsp``
    (Serena), or ``both``. Persisted in ``~/.pathly`` via app_settings and read at
    call time, so flipping it takes effect without a server restart.

    The default is ``auto`` (not ``off``) so code-intelligence just-works wherever
    its external tools are installed — with no manual toggle, and no misleading
    "on but silently dead" state on a machine that has neither (``auto`` → ``none``
    there, which safely degrades to Grep/Read).
    """
    key = _get_setting("code_context.backend", "auto").strip().lower()
    if key == "auto":
        return _auto_backend()
    return key if key in ("cli", "lsp", "both") else "none"


def _auto_backend() -> str:
    """Resolve ``auto`` by probing which external code-intel tool is installed:
    prefer the graph (``cli`` / codebase-memory-mcp) for headless breadth, else
    fall back to ``lsp`` (Serena, launched via ``uvx``), else ``none``.

    A pure PATH probe (:func:`shutil.which`) — never raises. The backends are NOT
    pip deps, so a machine with neither cleanly resolves to ``none`` (Grep/Read
    fallback) instead of a config that claims to be on while doing nothing.
    """
    try:
        if shutil.which(_resolve_tool()):
            return "cli"
        if shutil.which("uvx"):
            return "lsp"
    except Exception:
        pass
    return "none"


def _resolve_tool() -> str:
    """The code-context CLI backend's binary name — always ``codebase-memory-mcp``.

    ``codebase-memory-mcp`` is Pathly's single cross-platform code-graph engine (symbols,
    callers/callees, call paths, impact; 158 languages). It is the ONLY supported tool —
    ``gitnexus`` was removed. Kept as a function (not a constant) so a future multi-tool setting
    could slot back in here; any legacy ``code_context.tool`` value is ignored."""
    return "codebase-memory-mcp"


# --- Backend dependency probing ----------------------------------------------
# Each real backend needs an external launcher, and each already degrades to "" when
# it is absent (``CliProvider.build_block`` → ``shutil.which(self.tool)``;
# ``SerenaSession.start`` → ``shutil.which(argv[0])``). That is the correct RUNTIME
# behavior — never raise, let the agent fall back to Grep — but at the API boundary it
# erased the difference between "the launcher is not installed" and "the backend ran
# and found nothing": ``/code/query`` returned ``{"ok": true, "result": null,
# "backend": "cli"}`` for both, and a non-``none`` ``backend`` value reads as though a
# backend actually ran. These helpers name the gap so a caller can report a fixable
# setup problem instead of silently degrading forever.

# backend -> (launcher binary, how to install it)
_BACKEND_DEPS: dict[str, tuple[str, str]] = {
    "cli": (
        "codebase-memory-mcp",
        "install the codebase-memory-mcp binary and put it on PATH",
    ),
    "lsp": ("uvx", "install uv (provides uvx) — https://docs.astral.sh/uv/"),
}


def missing_dependencies(backend: str) -> list[dict[str, str]]:
    """Launchers the effective ``backend`` needs but that are not on PATH.

    Returns ``[]`` when everything the backend needs is present (and for ``none``,
    which needs nothing). Never raises — a probe failure reports "nothing missing"
    so this can only ever ADD information to a response, never break one.
    """
    import shutil

    key = (backend or "none").strip().lower()
    if key == "off":
        key = "none"
    wanted = ["cli", "lsp"] if key == "both" else [key]
    out: list[dict[str, str]] = []
    for name in wanted:
        dep = _BACKEND_DEPS.get(name)
        if dep is None:
            continue
        binary, hint = dep
        if name == "lsp":
            # Honor a PATHLY_SERENA_ARGV override rather than assuming uvx.
            try:
                from .serena_session import serena_argv

                binary = serena_argv()[0] or binary
            except Exception:
                logger.debug("code_context: serena_argv probe failed", exc_info=True)
        try:
            if shutil.which(binary) is None:
                out.append({"backend": name, "binary": binary, "install": hint})
        except Exception:
            logger.debug("code_context: which(%r) failed", binary, exc_info=True)
    return out


def _resolve_reindex() -> str:
    """Return the ``code_context.reindex`` setting: ``off | stage | auto``.

    Defaults to ``auto``. ``stage`` = Pathly re-indexes at each stage boundary;
    ``auto`` = let the tool self-index (``auto_index``); ``off`` = never.
    """
    key = _get_setting("code_context.reindex", "auto").strip().lower()
    return key if key in ("off", "stage", "auto") else "auto"


_auto_index_done = False
_last_reindex_monotonic = 0.0
# Re-index at most this often. The incremental index is cheap (hash-based — only
# changed files reparse), but we still debounce so frequent /code/query calls (which
# now trigger this) never spawn a subprocess per request.
_REINDEX_DEBOUNCE_S = 30.0


def maybe_reindex(project_root: str) -> None:
    """Freshness bridge — fire-and-forget incremental re-index per ``code_context.reindex``.

    Called per stage from runner prompt assembly AND on-demand from the /code/query
    route. Only acts for the cli/codebase-memory-mcp backend; **never raises, never
    blocks** (runs in a daemon thread); debounced to at most once per
    ``_REINDEX_DEBOUNCE_S``.

    Both ``stage`` and ``auto`` run ``index_repository`` (incremental: persisted hashes
    mean only changed files reparse); ``auto`` additionally sets the tool's own
    ``auto_index`` once. ``off`` → nothing.

    NB ``auto`` USED to only flip the tool's ``auto_index`` flag and defer freshness to
    the tool — but the tool's change-detection silently misses edits (``detect_changes``
    can report 0 changed for genuinely-changed files), so the graph drifted stale.
    ``auto`` now re-indexes itself.
    """
    global _auto_index_done, _last_reindex_monotonic
    try:
        if _resolve_backend() != "cli" or _resolve_reindex() == "off":
            return
        if _resolve_tool() != "codebase-memory-mcp":
            return
        exe = shutil.which("codebase-memory-mcp")
        if not exe:
            return
        now = time.monotonic()
        if now - _last_reindex_monotonic < _REINDEX_DEBOUNCE_S:
            return
        _last_reindex_monotonic = now

        root = os.path.abspath(project_root or os.getcwd()).replace("\\", "/")
        argvs: list[list[str]] = []
        if _resolve_reindex() == "auto" and not _auto_index_done:
            _auto_index_done = True
            argvs.append([exe, "config", "set", "auto_index", "true"])
        argvs.append([exe, "cli", "index_repository", json.dumps({"repo_path": root})])

        def _bg() -> None:
            for a in argvs:
                try:
                    subprocess.run(a, capture_output=True, text=True, timeout=180)
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
    project_root: str = "",
    backend: str | None = None,
) -> str:
    """Return an advisory ``## Code structure`` block for ``files``, or ``""``.

    **Never raises.** Any failure returns ``""`` (the "never break the prompt"
    idiom); the default backend is ``none`` (safe-off).

    ``project_root`` anchors relative ``files`` (agents pass the repo-relative
    changed-set) — without it the ``cli`` backend resolves paths against the
    server's process CWD and silently finds nothing.

    ``backend`` overrides the configured backend for this call (the proxy maps
    its ``engine`` param to ``cli``/``lsp``/``both``); ``None`` uses the persisted
    ``code_context.backend`` setting.
    """
    try:
        provider = get_provider(backend if backend is not None else _resolve_backend())
        return provider.build_block(
            scope,
            list(files or []),
            role or "",
            int(budget),
            project_root or "",
        )
    except Exception:
        logger.debug(
            "code_context: build_block failed — returning empty block",
            exc_info=True,
        )
        return ""
