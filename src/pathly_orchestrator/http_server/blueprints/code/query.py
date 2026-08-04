"""Code-intelligence proxy endpoint (POST /code/query).

Approach C of the code-intelligence initiative: an agent (interactive or runner,
any role) asks Pathly for code structure over HTTP, and Pathly proxies the query
to the shared ``runner.code_context`` backend. It is one more endpoint on the FSM
HTTP server every agent already reaches via ``pathly-fsm-call`` — no new
transport, no dependency on the host exposing MCP tools to sub-agents.

Phase 6 (this commit) ships the route over the shared backend, returning a
**safe-null** envelope when the backend is off (the default). Later phases layer
on top without rewriting this handler:

* Phase 8 — role allowlist (``code_intel.roles``) + per-op tiering.
* Phase 9 — gateway content-hash cache + comms-board logging per query.

Safety contract (from the code-intel-proxy APPROACH): the endpoint **never 500s
on a backend miss** — a missing/disabled backend returns
``{"ok": true, "result": null, "backend": "none"}`` so the agent degrades to
Grep instead of crashing. Only a malformed *request* gets a 4xx.
"""

from __future__ import annotations

import hashlib
import logging
import os

from flask import Blueprint, jsonify, request

logger = logging.getLogger("pathly.http")

bp = Blueprint("code", __name__)

# Soft char budget for the returned block when a real backend is active. Mirrors
# runner.code_context._DEFAULT_BUDGET; callers may override via the request body.
_DEFAULT_BUDGET = 1500

# Optional per-request ``engine`` → backend mapping. Lets ONE endpoint serve the
# graph (codebase-memory-mcp, breadth), the LSP (Serena, always-fresh), or both.
# Absent / unknown → fall through to the configured ``code_context.backend``.
_ENGINE_TO_BACKEND = {"graph": "cli", "cli": "cli", "lsp": "lsp", "both": "both"}

# --- Role -> capability tiering (Approach C "code_intel.roles") ---------------
# The gateway gates each query by the caller's role per the code-intel-proxy
# APPROACH. Each role maps to a tier; each tier grants a set of ops. Excluded
# (and unknown/empty) roles get a safe-null with reason="disabled"; a known role
# requesting an op outside its tier gets reason="op-not-permitted". A config-
# driven `code_intel.roles` override is a future refinement — these are the
# defaults from the APPROACH.
_TIER_OPS: dict[str, frozenset[str]] = {
    # full — impact + callers + chain (superset also covers the lookup ops)
    "full": frozenset({"impact", "callers", "chain", "symbol", "context", "pattern"}),
    # chain — call-chain tracing only
    "chain": frozenset({"chain"}),
    # lookup — symbol + context only
    "lookup": frozenset({"symbol", "context"}),
}
_ROLE_TIER: dict[str, str] = {
    "architect": "full",
    "builder": "full",
    "reviewer": "full",
    "explorer": "full",
    # "worker"/"explorer" are the FSM/loop host-neutral roles (agent_hint.role); a
    # worker does implementation → full, like builder. Without this, a loop task agent
    # that passes its host-neutral role was silently gated and code-query never fired.
    "worker": "full",
    "scout": "chain",
    "tester": "chain",
    "quick": "lookup",
    "director": "lookup",
    "planner": "lookup",
    "designer": "lookup",
    "po": "lookup",
    "web-researcher": "excluded",
    "orchestrator": "excluded",
    "evaluator": "excluded",
    "human": "excluded",
}

# Fallback tier for an unrecognized / empty role. A Pathly agent that didn't name its
# role (e.g. a loop task agent) must still get BASIC, board-logged code-query — a silent
# "disabled" no-op is why code-query never fired in loop runs. Only EXPLICITLY excluded
# roles are denied outright.
_DEFAULT_TIER = "lookup"


def _gate(role: str, op: str) -> str | None:
    """Return a denial reason, or None when (role, op) is permitted.

    An EXPLICITLY excluded role (web-researcher, orchestrator, evaluator, human) is
    denied ``"disabled"``. An unknown / empty role falls back to the ``lookup`` tier —
    it still gets basic, logged code-query instead of a silent off. A known role
    requesting an op outside its tier is denied ``"op-not-permitted"``.
    """
    tier = _ROLE_TIER.get(role.strip().lower())
    if tier == "excluded":
        return "disabled"
    if tier is None:
        tier = _DEFAULT_TIER
    if op.strip().lower() not in _TIER_OPS[tier]:
        return "op-not-permitted"
    return None


# --- Gateway content-hash cache + board logging ------------------------------
# Cache key is (op, target, content-hash): a repeated query for an UNCHANGED
# file is served without re-querying the backend; editing the file changes the
# hash and forces a fresh query. Gateway-local for now — when Phase 3 lands a
# content-hash cache inside runner.code_context, this should delegate to it.
_QUERY_CACHE: dict[tuple[str, str, str, str], "str | None"] = {}


def _content_hash(target: str, project_root: str) -> str:
    """SHA1 of the target file's bytes, or '' when it can't be read.

    A stable '' hash still caches per-target (just not content-sensitive), so a
    missing or symbol-style target degrades gracefully instead of disabling the
    cache.
    """
    try:
        path = (
            target
            if os.path.isabs(target)
            else os.path.join(project_root or "", target)
        )
        with open(path, "rb") as fh:
            return hashlib.sha1(fh.read(), usedforsecurity=False).hexdigest()
    except Exception:
        return ""


def _query_log_text(op: str, target: str, role: str, backend: str, hit: bool) -> str:
    """The board-log line for one code query.

    ``hit`` records whether the backend actually returned structure (``hit``) or
    came back empty (``miss``). This is the observability signal: ``backend=cli``
    alone means the backend is *wired*; the ``hit``/``miss`` marker is what tells a
    human watching the board whether the query got *usable data* (or degraded to
    Grep). Pure/stateless so it is unit-testable without a DB.
    """
    return (
        f"code-query: {op} {target} "
        f"(role={role or '?'}, backend={backend}, {'hit' if hit else 'miss'})"
    )


def _log_query(
    scope: str, op: str, target: str, role: str, backend: str, hit: bool
) -> None:
    """Log a fresh code query to the comms board as a discovery (best-effort).

    Makes code lookups shared board context. Never raises — a logging failure
    must not break the gateway response (the never-500 contract).

    Skips non-board sentinel scopes — an empty scope, or a parenthesized marker like
    "(interactive)" (the main assistant's ad-hoc queries) — so exploratory lookups don't
    post noise; only real feature/goal scopes become shared board context.
    """
    if not scope or not scope.strip() or scope.strip().startswith("("):
        return
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.comms import post_message

        post_message(
            get_db(),
            board="project",
            scope=scope or "",
            from_agent="code-intel",
            type="discovery",
            text=_query_log_text(op, target, role, backend, hit),
        )
    except Exception:
        logger.debug("code_query: board logging failed", exc_info=True)


@bp.route("/code/query", methods=["POST"])
def code_query():
    """Proxy a ``{op, target}`` code-structure query to the shared backend.

    Request body (JSON): ``{"op": "impact|callers|symbol|pattern",
    "target": "<path-or-symbol>", "role": "<agent-role>", "scope": "<feature>",
    "engine": "graph|lsp|both", "budget": <int>}``. ``op`` and ``target`` are
    required; the rest are optional. ``engine`` selects the backend for this
    request (graph = codebase-memory-mcp, lsp = Serena, both = merged); when
    omitted the configured ``code_context.backend`` is used. Returns
    ``{ok, op, target, result, backend}`` — ``result`` is the advisory block
    string, or ``null`` when the backend is off / has nothing.
    """
    try:
        # http_server -> runner is an allowed (downward) import; keep it lazy
        # inside the handler like the comms blueprints — fast startup, no cycles.
        from pathly_orchestrator.runner import code_context as _cc

        data = request.get_json(silent=True)
        if not isinstance(data, dict) or not data:
            return jsonify({"error": "Missing or invalid JSON body"}), 400

        op = data.get("op", "")
        target = data.get("target", "")
        if not isinstance(op, str) or not op.strip():
            return jsonify({"error": "Field 'op' must be a non-empty string"}), 400
        if not isinstance(target, str) or not target.strip():
            return jsonify({"error": "Field 'target' must be a non-empty string"}), 400

        role = data.get("role") or ""
        scope = data.get("scope") or data.get("feature") or ""
        try:
            budget = int(data.get("budget") or _DEFAULT_BUDGET)
        except (TypeError, ValueError):
            budget = _DEFAULT_BUDGET

        # Optional engine override — unifies graph + lsp under this one endpoint.
        # None when unset/unknown → build_block uses the configured backend.
        engine = str(data.get("engine") or "").strip().lower()
        backend_override = _ENGINE_TO_BACKEND.get(engine)

        # Role allowlist (Approach C): deny excluded roles and out-of-tier ops up
        # front with a safe-null + reason, before touching the backend.
        denial = _gate(role, op)
        if denial is not None:
            return (
                jsonify(
                    {
                        "ok": True,
                        "op": op.strip(),
                        "target": target.strip(),
                        "result": None,
                        "reason": denial,
                        "role": role,
                    }
                ),
                200,
            )

        # Effective backend for THIS request: an explicit `engine` wins, else the
        # persisted `code_context.backend` setting (off→none | cli | lsp | both),
        # read live so flipping it takes effect without a restart.
        effective = backend_override or _cc._resolve_backend()
        backend = _cc.get_provider(effective).name

        # On-demand freshness: fire a debounced background re-index so the graph keeps
        # up with edits between pipeline stages. No-op when the backend is off or inside
        # the debounce window; never blocks. (The tool's own auto_index silently misses
        # edits, so we drive the incremental index ourselves.)
        _cc.maybe_reindex(str(data.get("project_root") or ""))

        # Content-hash cache: serve an unchanged (op, target) from cache without
        # re-querying the backend; an edit changes the hash and forces a refresh.
        # The backend is part of the key — an lsp query must not be served a cached
        # graph result for the same file (they carry different structure).
        chash = _content_hash(target, str(data.get("project_root") or ""))
        key = (op.strip().lower(), target.strip(), chash, backend)
        cached = key in _QUERY_CACHE
        if cached:
            result = _QUERY_CACHE[key]
        else:
            # build_block never raises and returns "" when the backend is off;
            # map an empty block to JSON null so the agent gets a safe-null.
            block = _cc.build_block(
                scope,
                [target],
                role,
                budget,
                str(data.get("project_root") or ""),
                backend=backend_override,
            )
            result = block or None
            # Cache only NON-empty results. A null (backend off, LSP still warming
            # up, or a file whose repo hasn't finished the graph's async auto-onboard)
            # must NOT be pinned — otherwise the first file queried during indexing
            # stays null until its content hash changes. Re-querying a null is cheap
            # and lets the block appear the moment the index lands. (Mirrors
            # CliProvider._file_section, which likewise caches only non-empty sections.)
            if result is not None:
                _QUERY_CACHE[key] = result
            # Log fresh queries to the board (shared context) with a hit/miss marker
            # so the board shows whether the backend returned data. Cache hits are not
            # re-logged — the board already carries the prior entry.
            _log_query(scope, op.strip(), target.strip(), role, backend, bool(result))

        payload = {
            "ok": True,
            "op": op.strip(),
            "target": target.strip(),
            "result": result,
            "backend": backend,
            "cached": cached,
        }
        # A null result has two very different causes: the backend ran and found
        # nothing, or the backend's launcher isn't installed at all. Both used to
        # look identical (`backend: "cli", result: null`), which reads as though a
        # backend ran — so a broken setup degraded to Grep silently and forever.
        # Name the second case; the safe-null contract is unchanged (still ok:true,
        # still 200, still result:null) — this only ADDS a diagnosis.
        if result is None:
            missing = _cc.missing_dependencies(effective)
            if missing:
                payload["reason"] = "backend-unavailable"
                payload["missing"] = missing
        return jsonify(payload), 200
    except Exception as exc:
        # Never surface a 500 to the agent on a backend miss — degrade to
        # safe-null so the caller falls back to Grep. (Malformed requests already
        # returned 4xx above.)
        logging.exception("code_query error")
        return (
            jsonify(
                {
                    "ok": True,
                    "result": None,
                    "backend": "none",
                    "error_type": type(exc).__name__,
                }
            ),
            200,
        )
