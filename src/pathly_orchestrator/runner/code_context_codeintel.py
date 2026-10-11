"""The ``codeintel`` code-intelligence backend (split out of ``code_context.py``).

Delegates ``/code/query`` to **codeintel** (``pip install codecortex``), which
answers the op the agent actually asked — real ``callers`` / ``callees`` /
``impact`` / ``chain`` rows (each marked ``resolved`` vs ``name-matched``),
LSP ``symbol`` lookups, and semantic ``search`` — instead of the per-file
symbol-count summary the ``cli`` / ``lsp`` backends return for every op.

Two transports, tried in order:

1. **HTTP** — a long-lived ``codeintel serve-http`` daemon
   (``code_context.codeintel_url``, default ``http://127.0.0.1:8766``). Preferred:
   its LSP session and embedding model stay warm across queries.
2. **Subprocess** — ``codeintel query --json`` (one-shot). Works with nothing
   running, but pays the LSP / embedding warm-up on every call.

For prompt injection (``build_block`` over in-scope *files*) this backend reuses
the ``cli`` file-structure block: codeintel's graph engine reads the same
codebase-memory-mcp index, and its ops are symbol-targeted, not file-targeted.

Never raises: every failure degrades to ``None`` / ``""`` so the caller falls
back to Grep/Read, matching the rest of ``code_context``.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from typing import Any

from .code_context_cli import CliProvider

logger = logging.getLogger(__name__)

_DEFAULT_URL = "http://127.0.0.1:8766"
_HTTP_TIMEOUT_S = 30
# One-shot CLI: the first ``lsp`` / ``search`` query on a cold machine boots
# serena / loads the embedding model, so allow well over the HTTP timeout.
_CLI_TIMEOUT_S = 120

#: Engines codeintel understands; anything else is sent as ``auto``.
CODEINTEL_ENGINES = frozenset({"auto", "graph", "lsp", "semantic", "both", "all"})


def _setting(key: str, default: str) -> str:
    """Late-bound app_settings read (shared helper lives in ``code_context``)."""
    try:
        from .code_context import _get_setting

        return _get_setting(key, default)
    except Exception:
        return default


def _query_http(url: str, body: dict[str, Any], token: str) -> dict[str, Any] | None:
    """POST to a running ``codeintel serve-http``; ``None`` when unreachable."""
    req = urllib.request.Request(
        url.rstrip("/") + "/code/query",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT_S) as resp:
            out = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:  # 401/403/404 still carry a JSON body
        try:
            out = json.loads(exc.read().decode("utf-8"))
        except Exception:
            return None
    except Exception:
        return None  # daemon not running -> caller tries the subprocess
    return out if isinstance(out, dict) else None


def _query_cli(body: dict[str, Any]) -> dict[str, Any] | None:
    """Run ``codeintel query --json`` one-shot; ``None`` when not installed/failed."""
    exe = shutil.which("codeintel")
    if not exe:
        return None
    argv = [exe, "query", "--op", body["op"], "--target", body["target"], "--json"]
    if body.get("engine"):
        argv += ["--engine", body["engine"]]
    if body.get("project_root"):
        argv += ["--project-root", body["project_root"]]
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=_CLI_TIMEOUT_S, check=False)
        out = json.loads(proc.stdout) if proc.stdout.strip() else None
    except Exception:
        return None
    return out if isinstance(out, dict) else None


def _render(envelope: dict[str, Any]) -> str:
    """Turn codeintel's envelope into the proxy's advisory text block."""
    body = envelope.get("result")
    if body is None:
        return ""
    text = body if isinstance(body, str) else json.dumps(body, indent=2)
    notes = []
    if envelope.get("confidence") == "partial":
        notes.append("partial answer — see codeintel `gaps`")
    if envelope.get("reindexing"):
        notes.append("served from the last completed index (reindex running)")
    head = "## codeintel (advisory — `resolved` rows are evidence, `name-matched` are leads)"
    if notes:
        head += "\n> " + "; ".join(notes)
    return head + "\n" + text


class CodeintelProvider:
    """``codeintel`` backend: op-aware ``query`` + file-structure ``build_block``."""

    name = "codeintel"

    def __init__(
        self,
        http: Callable[[str, dict[str, Any], str], dict[str, Any] | None] = _query_http,
        cli: Callable[[dict[str, Any]], dict[str, Any] | None] = _query_cli,
    ) -> None:
        self._http = http
        self._cli = cli

    def build_block(
        self,
        scope: str,
        files: Sequence[str],
        role: str,
        budget: int,
        project_root: str = "",
    ) -> str:
        return CliProvider().build_block(scope, files, role, budget, project_root)

    def query(
        self,
        op: str,
        target: str,
        project_root: str = "",
        engine: str = "",
        budget: int = 6000,
    ) -> tuple[str, dict[str, Any]]:
        """Answer ``op`` on ``target``. Returns ``(block, meta)`` — never raises.

        ``block`` is ``""`` on a null answer; ``meta`` carries codeintel's
        ``reason`` / ``hint`` / ``outcome`` (and ``transport``) for the proxy
        to surface, so "not indexed" is distinguishable from "no callers".
        """
        try:
            eng = (engine or "auto").strip().lower()
            body: dict[str, Any] = {
                "op": op.strip(),
                "target": target.strip(),
                "engine": None if eng not in CODEINTEL_ENGINES or eng == "auto" else eng,
                "project_root": os.path.abspath(project_root) if project_root else "",
            }
            url = _setting("code_context.codeintel_url", _DEFAULT_URL)
            token = os.environ.get("CODEINTEL_TOKEN") or _setting(
                "code_context.codeintel_token", ""
            )
            envelope, transport = self._http(url, body, token), "http"
            if envelope is None:
                envelope, transport = self._cli(body), "cli"
            if envelope is None:
                return "", {"reason": "backend-unavailable", "transport": "none"}
            meta = {k: envelope[k] for k in ("reason", "hint", "outcome", "engine") if k in envelope}
            meta["transport"] = transport
            return _render(envelope)[: max(0, int(budget))], meta
        except Exception:
            logger.debug("codeintel: query failed", exc_info=True)
            return "", {"reason": "backend-error", "transport": "none"}
