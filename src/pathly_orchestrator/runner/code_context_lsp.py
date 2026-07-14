"""The ``lsp`` code-intelligence backend — Serena (LSP) behind ``/code/query``.

Companion to :mod:`.code_context_cli` (the ``cli`` / codebase-memory-mcp graph
backend). Where the graph backend gives *breadth* (whole-repo symbols + caller/
callee counts, but can lag recent edits), this backend gives LSP *precision that
is always fresh* — top-level symbols read live from the language server through
Serena's MCP tools.

The MCP transport (subprocess + JSON-RPC handshake) lives in
:mod:`.serena_session`; this module owns the *provider*: a single cached session
with **async warm-up**, path/shape rendering, and the never-raise contract. A
Serena boot is slow (seconds+), so the first ``build_block`` for a project
returns ``""`` (warm-up → the caller degrades to Grep, exactly like the graph
backend's async re-index) and later calls return real LSP structure once ready.

Contract (mirrors the rest of ``code_context``): **never raises**, deadline-
bounded, degrades to ``""`` on any failure. One cached session at a time;
switching ``project_root`` tears the old one down. A failed boot is retried only
after a cooldown so a broken Serena install can't spawn a slow subprocess per
request.
"""

from __future__ import annotations

import atexit
import json
import os
import threading
import time
from typing import Sequence

from .serena_session import SerenaSession

_MAX_FILES = 2  # cap files queried per block (mirror CliProvider)
_OVERVIEW_LIMIT = 12  # symbols rendered per file
_FAIL_COOLDOWN_S = 60.0  # after a failed boot, wait this long before retrying


# --- module-level single cached session (async warm-up) -------------------
_session: SerenaSession | None = None
_session_root = ""
_session_state = "idle"  # idle | starting | ready | failed
_last_start_monotonic = 0.0
_state_lock = threading.Lock()


def _abs_root(project_root: str, sample_file: str) -> str:
    """Absolute project root for the Serena session (anchors ``--project``)."""
    if project_root:
        return os.path.abspath(project_root).replace("\\", "/")
    if os.path.isabs(sample_file):
        return os.path.dirname(sample_file).replace("\\", "/")
    return os.getcwd().replace("\\", "/")


def _start_session_bg(root: str) -> None:
    """Boot a session in a daemon thread; publish it only if still the wanted root."""
    global _session, _session_state
    sess = SerenaSession(root)
    ok = sess.start()
    with _state_lock:
        if _session_root != root:
            # A newer project_root superseded this boot while it ran — discard it.
            try:
                sess.close()
            except Exception:
                pass
            return
        if ok:
            _session = sess
            _session_state = "ready"
        else:
            _session = None
            _session_state = "failed"


def _get_ready_session(root: str) -> "SerenaSession | None":
    """A ready session for ``root``, or ``None`` after kicking off an async boot.

    One session at a time: a different root replaces the old one. Returns ``None``
    during boot (warm-up) and during the post-failure cooldown, so the caller
    degrades to Grep instead of blocking.
    """
    global _session, _session_root, _session_state, _last_start_monotonic
    now = time.monotonic()
    with _state_lock:
        if _session_state == "ready" and _session_root == root and _session:
            return _session
        if _session_state == "starting" and _session_root == root:
            return None  # boot in flight
        if (
            _session_state == "failed"
            and _session_root == root
            and now - _last_start_monotonic < _FAIL_COOLDOWN_S
        ):
            return None  # cooldown after a failed boot — don't respawn per request
        if _session is not None:
            try:
                _session.close()
            except Exception:
                pass
            _session = None
        _session_root = root
        _session_state = "starting"
        _last_start_monotonic = now
    threading.Thread(target=_start_session_bg, args=(root,), daemon=True).start()
    return None


def _relativize(path: str, root: str) -> str:
    """Repo-relative form of ``path`` for Serena's ``relative_path`` argument."""
    p = path.replace("\\", "/")
    r = root.rstrip("/")
    if os.path.isabs(p) and r and p.startswith(r + "/"):
        return p[len(r) + 1 :]
    return p


def _render_overview(path: str, text: str, limit: int) -> str:
    """Render a Serena ``get_symbols_overview`` payload into a ``### file`` section.

    Serena's live shape (verified 1.27.0) is a dict of **kind → list of name
    strings** — e.g. ``{"Class": ["Widget"], "Function": ["make_widget",
    "main"]}``. Also tolerate a ``{"symbols": [ {name_path, kind}, … ]}`` wrapper
    and a bare list-of-dicts (older/other shapes), and degrade to ``""`` on
    anything unparseable or empty.
    """
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return ""
    lines: list[str] = []

    def _add(name, kind=None) -> None:
        if isinstance(name, str) and name:
            lines.append(f"- {name}" + (f"  (kind:{kind})" if kind else ""))

    if isinstance(data, dict) and isinstance(data.get("symbols"), list):
        data = data["symbols"]
    if isinstance(data, dict):
        # kind -> [name, ...]  (the live Serena shape)
        for kind, names in data.items():
            if not isinstance(names, list):
                continue
            for n in names:
                if isinstance(n, dict):
                    _add(n.get("name_path") or n.get("name"), n.get("kind") or kind)
                else:
                    _add(n, kind)
    elif isinstance(data, list):
        for sym in data:
            if isinstance(sym, dict):
                _add(sym.get("name_path") or sym.get("name"), sym.get("kind"))
            else:
                _add(sym)
    lines = lines[:limit]
    return (f"### {path}\n" + "\n".join(lines)) if lines else ""


class LspProvider:
    """``lsp`` backend over Serena — always-fresh top-level symbols per file.

    The first call for a project boots Serena asynchronously and returns ``""``
    (warm-up); once ready, later calls return an advisory block. Never raises.
    """

    name = "lsp"

    def build_block(
        self,
        scope: str,
        files: Sequence[str],
        role: str,
        budget: int,
        project_root: str = "",
    ) -> str:
        del scope, role  # steering happens at the gateway, not the raw query
        try:
            flist = list(files or [])
            if not flist:
                return ""
            root = _abs_root(project_root, flist[0])
            sess = _get_ready_session(root)
            if sess is None:
                return ""  # warming up (or in cooldown) → degrade to Grep
            sections: list[str] = []
            for path in flist[:_MAX_FILES]:
                rel = _relativize(path, root)
                text = sess.call_tool("get_symbols_overview", {"relative_path": rel})
                if text:
                    section = _render_overview(rel, text, _OVERVIEW_LIMIT)
                    if section:
                        sections.append(section)
            if not sections:
                return ""
            block = "## Code structure — LSP (advisory, always-fresh)\n" + "\n\n".join(
                sections
            )
            return block[: max(0, int(budget))]
        except Exception:
            return ""


def _close_session_atexit() -> None:
    """Tear the cached Serena subprocess down on interpreter exit (best-effort)."""
    global _session
    if _session is not None:
        try:
            _session.close()
        except Exception:
            pass
        _session = None


atexit.register(_close_session_atexit)
