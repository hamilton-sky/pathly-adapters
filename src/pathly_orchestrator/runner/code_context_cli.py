"""The ``cli`` code-intelligence backend (split out of ``code_context.py``).

Queries **codebase-memory-mcp**'s pre-built code graph for the in-scope files —
each file's functions/methods/classes with their caller (``in_degree``) and
callee (``out_degree``) counts. This file owns exactly one concern: "shell out
to the code-graph CLI and render an advisory structure block". ``code_context``
owns the interface, config, and dispatch and imports :class:`CliProvider` here.

Degrades to ``""`` on every failure (missing binary, un-indexed repo, query
error, timeout) and never hangs — so the ``cli`` backend is always safe to
enable. Mirrors the never-raise contract of the rest of code_context.
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import os
import shutil
import subprocess
from typing import Sequence

from pathly_orchestrator.scope_names import cache_root

# Bounds — keep the shell-out cheap and never let it hang the prompt: at most N
# files queried, each query deadline-capped (the graph binary is fast, but the
# deadline is the backstop against a wedged process).
_CLI_TIMEOUT_S = 8
_CLI_MAX_FILES = 2

# Content-hash cache. Key = (project root, path, sha1-of-bytes), value = the rendered
# per-file structure section. An UNCHANGED file is reused without re-querying; an edit
# changes the hash and forces a refresh. The project is part of the key: a relative path
# with the same bytes is the same key in every project, and each project's graph answers
# for its own symbols. Only NON-empty sections are cached, and only for a file that has a
# hash, so a query made before the repo is indexed is not frozen as "no data".
_CLI_CACHE: dict[tuple[str, str, str], str] = {}


def _cypher_literal(text: str) -> str | None:
    """``text`` as the inside of a double-quoted Cypher string, or None when it holds a double
    quote. A quote cannot be made part of the string without trusting that the tool's lexer
    reads a backslash before it as an escape (the real ``codebase-memory-mcp`` was not available
    to check), and a quote that ends the literal lets a request's target add conditions, so the
    caller makes no query for such a text. A backslash is doubled.
    """
    if '"' in text:
        return None
    return text.replace("\\", "\\\\")


def _file_hash(path: str, project_root: str = "") -> str:
    """SHA1 of the file's bytes, or ``""`` when it can't be read. A relative ``path`` is read
    under ``project_root`` (the project the call names), not the server's working directory.
    """
    if project_root and not os.path.isabs(path):
        path = os.path.join(project_root, path)
    try:
        with open(path, "rb") as fh:
            return hashlib.sha1(fh.read(), usedforsecurity=False).hexdigest()
    except OSError:
        return ""


def _await_or_empty(fut: "concurrent.futures.Future[str]") -> str:
    """Return the future's result, or ``""`` if it overruns the deadline.

    The backstop for a code-intel CLI that hangs: a subprocess timeout does not
    reliably kill a tool's whole process tree (notably on Windows), so the
    calling thread bounds the WAIT and degrades to ``""`` — the response stays
    bounded even when the tool won't die ("never hang the prompt").
    """
    try:
        return fut.result(timeout=_CLI_TIMEOUT_S + 2)
    except Exception:
        return ""


class CliProvider:
    """``cli`` backend over **codebase-memory-mcp**: queries the pre-built code
    graph for the in-scope files' symbols + caller/callee counts.

    The repo must be indexed first (``codebase-memory-mcp cli index_repository``);
    ``code_context.maybe_reindex`` refreshes it at stage boundaries. The binary is
    always ``codebase-memory-mcp`` — Pathly's sole code-graph engine (gitnexus removed).
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
        project_root: str = "",
    ) -> str:
        # scope/role steer caching + per-role tiering at the gateway, not the
        # raw query — the cli backend only needs the files.
        del scope, role
        if not files:
            return ""
        exe = shutil.which(self.tool)
        if not exe:
            return ""  # binary not installed -> safe no-op
        project = self._project(exe, list(files)[0], project_root)
        if not project:
            return ""  # repo not indexed yet -> no block (caller degrades to Grep)
        sections: list[str] = []
        for path in list(files)[:_CLI_MAX_FILES]:
            section = self._file_section(exe, project, path, project_root)
            if section:
                sections.append(section)
        if not sections:
            return ""
        block = "## Code structure (advisory — verify before acting)\n" + "\n\n".join(
            sections
        )
        return block[: max(0, int(budget))]

    def _project(self, exe: str, sample_file: str, project_root: str = "") -> str:
        """Indexed project whose root contains ``sample_file`` (longest-prefix
        match), or ``""`` when the repo is not indexed.

        A relative ``sample_file`` (agents pass the repo-relative changed-set) is
        anchored to ``project_root``, NOT the server process CWD — the FSM server
        rarely runs from the repo root, so ``os.path.abspath`` would mislocate every
        relative file and silently drop the whole block.
        """
        out = self._run(exe, ["cli", "list_projects", "{}"])
        try:
            projects = json.loads(out).get("projects", []) if out else []
        except Exception:
            return ""
        if os.path.isabs(sample_file):
            target = sample_file.replace("\\", "/")
        elif project_root:
            target = os.path.join(project_root, sample_file).replace("\\", "/")
        else:
            target = os.path.abspath(sample_file).replace("\\", "/")
        target = target.rstrip("/")
        best_name, best_len = "", -1
        for proj in projects:
            root = str(proj.get("root_path") or "").replace("\\", "/").rstrip("/")
            if root and (target == root or target.startswith(root + "/")):
                if len(root) > best_len:
                    best_name, best_len = str(proj.get("name") or ""), len(root)
        return best_name

    def _file_section(
        self, exe: str, project: str, path: str, project_root: str = ""
    ) -> str:
        """Cached-or-fresh structure section for ``path`` (content-hash cache).
        One deadline-bounded graph query; only non-empty sections cached."""
        file_hash = _file_hash(path, project_root)
        key = (cache_root(project_root), path, file_hash)
        if file_hash and key in _CLI_CACHE:
            return _CLI_CACHE[key]
        # Match on the last two path segments so repo-relative vs absolute paths
        # both resolve against the graph's stored (index-root-relative) file_path.
        tail = "/".join(path.replace("\\", "/").rstrip("/").split("/")[-2:])
        literal = _cypher_literal(tail)
        if literal is None:
            return ""  # a name with a double quote is not put into a query
        cypher = (
            'MATCH (n) WHERE n.file_path CONTAINS "' + literal + '" '
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
