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

import concurrent.futures
import hashlib
import json
import logging
import os
import shutil
import subprocess
from typing import Protocol, Sequence, runtime_checkable

logger = logging.getLogger(__name__)

# Default char budget for the injected block (chars, a conservative ~tokens*4
# upper bound). Callers may pass a tighter budget per role/phase.
_DEFAULT_BUDGET = 1500

# `cli` backend bounds — keep the shell-out cheap and never let it hang the
# prompt: at most N files queried, each subprocess call hard-capped in seconds.
# Node-based tools (gitnexus) cost ~5s just on process startup, so the per-file
# impact+context pair runs CONCURRENTLY (see _file_section) to keep one query
# near a single call's latency rather than the sum.
_CLI_TIMEOUT_S = 8
_CLI_MAX_FILES = 2

# Phase 3 — content-hash cache for the cli backend. Key = (path, sha1-of-bytes),
# value = the rendered per-file structure section. An UNCHANGED file is reused
# without re-shelling-out to gitnexus; an edit changes the hash and forces a
# refresh. Mirrors the `indexed_hash` fingerprint idea from the context-retrieval
# spec. Only NON-empty sections are cached, so a query made before the index
# exists is not frozen as "no data" once the repo is later indexed.
_CLI_CACHE: dict[tuple[str, str], str] = {}


def _file_hash(path: str) -> str:
    """SHA1 of the file's bytes, or ``""`` when it can't be read."""
    try:
        with open(path, "rb") as fh:
            return hashlib.sha1(fh.read()).hexdigest()
    except OSError:
        return ""


def _await_or_empty(fut: "concurrent.futures.Future[str]") -> str:
    """Return the future's result, or ``""`` if it overruns the deadline.

    The backstop for a code-intel CLI that hangs: a subprocess timeout does not
    reliably kill a node tool's whole process tree (notably on Windows), so the
    calling thread bounds the WAIT and degrades to ``""`` — the response stays
    bounded even when the tool won't die ("never hang the prompt").
    """
    try:
        return fut.result(timeout=_CLI_TIMEOUT_S + 2)
    except Exception:
        return ""


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


class CliProvider:
    """``cli`` backend over **codebase-memory-mcp**: queries the pre-built code
    graph for the in-scope files — each file's functions/methods/classes with
    their caller (``in_degree``) and callee (``out_degree``) counts.

    Degrades to ``""`` on every failure mode — missing binary, un-indexed repo,
    query error, or timeout — so it is always safe to enable. Work is bounded
    (``_CLI_MAX_FILES`` files; each query deadline-capped) and never hangs.

    The repo must be indexed first (``codebase-memory-mcp cli index_repository``);
    Pathly re-indexes at stage boundaries (cheap — a static binary over SQLite).
    ``tool`` selects the binary name, so the source can be swapped through the
    ``code_context.tool`` setting (e.g. back to ``gitnexus`` on Linux/CI).
    """

    name = "cli"

    def __init__(self, tool: str = "codebase-memory-mcp") -> None:
        self.tool = tool

    def build_block(
        self,
        scope: str,
        files: Sequence[str],
        role: str,
        budget: int,
    ) -> str:
        # scope/role steer caching + per-role tiering at the gateway, not the
        # raw query — the cli backend only needs the files.
        del scope, role
        if not files:
            return ""
        exe = shutil.which(self.tool)
        if not exe:
            return ""  # binary not installed -> safe no-op
        project = self._project(exe, list(files)[0])
        if not project:
            return ""  # repo not indexed yet -> no block (caller degrades to Grep)
        sections: list[str] = []
        for path in list(files)[:_CLI_MAX_FILES]:
            section = self._file_section(exe, project, path)
            if section:
                sections.append(section)
        if not sections:
            return ""
        block = (
            "## Code structure (advisory — verify before acting)\n"
            + "\n\n".join(sections)
        )
        return block[: max(0, int(budget))]

    def _project(self, exe: str, sample_file: str) -> str:
        """Indexed project whose root contains ``sample_file`` (longest-prefix
        match), or ``""`` when the repo is not indexed."""
        out = self._run(exe, ["cli", "list_projects", "{}"])
        try:
            projects = json.loads(out).get("projects", []) if out else []
        except Exception:
            return ""
        target = os.path.abspath(sample_file).replace("\\", "/")
        best_name, best_len = "", -1
        for proj in projects:
            root = str(proj.get("root_path") or "").replace("\\", "/").rstrip("/")
            if root and (target == root or target.startswith(root + "/")):
                if len(root) > best_len:
                    best_name, best_len = str(proj.get("name") or ""), len(root)
        return best_name

    def _file_section(self, exe: str, project: str, path: str) -> str:
        """Cached-or-fresh structure section for ``path`` (Phase 3 content-hash
        cache). One deadline-bounded graph query; only non-empty sections cached."""
        file_hash = _file_hash(path)
        key = (path, file_hash)
        if file_hash and key in _CLI_CACHE:
            return _CLI_CACHE[key]
        # Match on the last two path segments so repo-relative vs absolute paths
        # both resolve against the graph's stored (index-root-relative) file_path.
        tail = "/".join(path.replace("\\", "/").rstrip("/").split("/")[-2:])
        cypher = (
            'MATCH (n) WHERE n.file_path CONTAINS "' + tail + '" '
            'AND n.label IN ["Function","Method","Class"] '
            "RETURN n.name, n.in_degree, n.out_degree "
            "ORDER BY n.in_degree DESC LIMIT 12"
        )
        payload = json.dumps({"project": project, "query": cypher})
        # Deadline-bounded so a stuck query can never block prompt assembly.
        pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            out = _await_or_empty(
                pool.submit(self._run, exe, ["cli", "query_graph", payload])
            )
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
        try:
            rows = json.loads(out).get("rows", []) if out else []
        except Exception:
            rows = []
        lines = [
            f"- {r[0]}  (callers:{r[1]}, callees:{r[2]})"
            for r in rows
            if isinstance(r, list) and len(r) >= 3 and r[0]
        ]
        section = (f"### {path}\n" + "\n".join(lines)) if lines else ""
        if file_hash and section:
            _CLI_CACHE[key] = section
        return section

    def _run(self, exe: str, args: list[str]) -> str:
        """Run ``<exe> <args…>`` and return trimmed stdout, or ``""`` on any
        failure (non-zero exit, timeout, OS error) — never raises."""
        try:
            proc = subprocess.run(
                [exe, *args],
                capture_output=True,
                text=True,
                timeout=_CLI_TIMEOUT_S,
                cwd=os.getcwd(),
            )
        except (subprocess.SubprocessError, OSError):
            return ""
        if proc.returncode != 0:
            return ""
        return (proc.stdout or "").strip()


# Static backend registry. ``none`` is a singleton; the ``cli`` backend is built
# on demand in :func:`get_provider` because it is parameterised by the
# ``code_context.tool`` setting (Phase 4). ``off`` maps to ``none``.
_PROVIDERS: dict[str, CodeContextProvider] = {
    "none": NoneProvider(),
}


def get_provider(backend: str | None) -> CodeContextProvider:
    """Return the provider for ``backend``, falling back to the ``none`` no-op.

    ``off`` / unknown / ``None`` resolve to :class:`NoneProvider` (safe-off).
    ``cli`` resolves to a :class:`CliProvider` configured with the current
    ``code_context.tool`` setting. A bad or stale value can never raise — it just
    disables the feature.
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

    Values: ``off`` (default, safe-off → ``none``) or ``cli`` (gitnexus
    querying). Persisted in ``~/.pathly`` via app_settings and read at call time,
    so flipping it takes effect without a server restart.
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
