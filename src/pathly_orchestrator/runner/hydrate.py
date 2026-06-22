"""Hydration engine for comms-board artifact sections (§4 + §3.4).

hydrate_section  — the primary entry point: resolve/create artifact row,
                   staleness check (mtime→hash→structure_key), ensure index,
                   slice the file, return a {body, status} dict.
ensure_indexed   — lazy index build (called by hydrate_section and by /section route).
index_artifact_async — daemon-thread eager indexer, mirrors embed_async.

NEVER raises to the caller — returns a result/status dict for every path.
.md ONLY (§8 item 0): early-return for non-.md before parsing.
"""

from __future__ import annotations

import logging
import os
import threading
import uuid

logger = logging.getLogger(__name__)


def _is_md(path: str) -> bool:
    """Return True when path has a .md extension (case-insensitive)."""
    return path.lower().endswith(".md")


def safe_plan_path(scope: str, artifact: str, project_root: str | None) -> str | None:
    """Resolve <project_root>/pathly/plans/<scope>/<artifact> and return the
    absolute path ONLY if it stays inside the plan-folder tree. Returns None on
    any traversal attempt. Rejects scope/artifact that contain a path separator,
    a '..' segment, or are absolute. Uses realpath + normcase containment."""
    if not project_root:
        return None
    for part, label in ((scope, "scope"), (artifact, "artifact")):
        if not part or not part.strip():
            return None
        if os.path.isabs(part):
            return None
        normalized = part.replace("\\", "/")
        if "/" in normalized or os.sep in normalized:
            return None
        if any(seg == ".." for seg in normalized.split("/")):
            return None
    root = os.path.realpath(os.path.join(project_root, "pathly", "plans", scope))
    candidate = os.path.realpath(os.path.join(root, artifact))
    root_nc = os.path.normcase(root)
    candidate_nc = os.path.normcase(candidate)
    if candidate_nc == root_nc or candidate_nc.startswith(root_nc + os.sep):
        return candidate
    return None


def _resolve_plan_root(scope: str, project_root: str | None = None) -> str:
    """Return the absolute path to pathly/plans/<scope>/.

    project_root is the repo root. Falls back to cwd-relative when absent.
    """
    base = project_root or os.getcwd()
    return os.path.normpath(os.path.join(base, "pathly", "plans", scope))


def _read_file_text(path: str) -> str | None:
    """Return file text, or None when unreadable."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


def ensure_indexed(
    conn,
    scope: str,
    path: str,
    project_root: str | None = None,
) -> dict:
    """Ensure the section index for path is up-to-date.  Returns a status dict.

    Handles:
    - Non-.md paths: early-return, no parse.
    - Path not on disk: return artifact_not_found.
    - First-time index: find_or_create_artifact_by_path, then parse + store.
    - Stale (mtime changed): re-parse; schedule async re-derive only on structure_key change.
    - Fresh (mtime unchanged): no-op.

    Staleness per §3.4: mtime → hash → structure_key, three independent gates.
    """
    from pathly_orchestrator.db.queries.comms import (
        find_or_create_artifact_by_path,
        reindex_artifact_sections,
        update_artifact_indexed_mtime,
    )
    from pathly_orchestrator.runner.sections import (
        Section,
        file_fingerprint,
        parse_sections,
        structure_key as compute_structure_key,
    )

    if not _is_md(path):
        return {"ok": True, "skipped": True, "reason": "non-md"}

    if not os.path.exists(path):
        return {"ok": False, "error": "artifact_not_found", "path": path}

    artifact = find_or_create_artifact_by_path(conn, scope, path)
    if artifact is None:
        return {"ok": False, "error": "artifact_not_found", "path": path}

    artifact_id = artifact["id"]
    stored_mtime = artifact.get("indexed_mtime")
    stored_hash = artifact.get("indexed_hash")
    stored_struct = artifact.get("indexed_structure_key")

    try:
        cur_mtime, cur_hash = file_fingerprint(path)
    except OSError as exc:
        return {"ok": False, "error": "stale_index", "detail": str(exc)}

    if stored_mtime is not None and abs(cur_mtime - stored_mtime) < 1e-6:
        return {"ok": True, "artifact_id": artifact_id, "stale_rebuilt": False}

    if stored_hash is not None and cur_hash == stored_hash:
        try:
            update_artifact_indexed_mtime(conn, artifact_id, cur_mtime)
        except Exception:
            pass
        return {"ok": True, "artifact_id": artifact_id, "stale_rebuilt": False}

    text = _read_file_text(path)
    if text is None:
        return {"ok": False, "error": "stale_index", "detail": f"cannot read {path}"}

    sections = parse_sections(text)
    cur_struct = compute_structure_key(sections)

    section_dicts = [
        {
            "id": str(uuid.uuid4()),
            "anchor": sec.anchor,
            "heading": sec.heading,
            "line_start": sec.line_start,
            "line_end": sec.line_end,
            "ordinal": sec.ordinal,
        }
        for sec in sections
    ]

    try:
        reindex_artifact_sections(
            conn, artifact_id, section_dicts, cur_mtime, cur_hash, cur_struct
        )
    except Exception as exc:
        return {"ok": False, "error": "stale_index", "detail": str(exc)}

    if stored_struct is not None and cur_struct != stored_struct:
        _schedule_resummarize_async(artifact_id)

    return {"ok": True, "artifact_id": artifact_id, "stale_rebuilt": True}


def _schedule_resummarize_async(artifact_id: str, backend: str | None = None) -> None:
    """Schedule async re-summarize of an artifact and its sections on structure change.

    `backend` overrides the summary backend for THIS run (per-upload choice); None
    falls back to the global app-setting. With the default (minilm/off) summarize
    returns None → no writeback → behavior byte-identical.

    Called when structure_key changes (heading added/removed/renamed). Fires a daemon
    thread that reads the artifact row, calls summarize_content for the whole artifact
    (topic-map) and each section (≤1 sentence), and writes back only when a non-None
    summary is returned. With backend=minilm (default) summarize_content returns None
    → no writeback → behavior byte-identical to the Phase 3 stub.
    """

    def _worker() -> None:
        try:
            from pathly_orchestrator.db.connection import get_db
            from pathly_orchestrator.db.queries.comms import (
                get_artifact_sections,
                update_artifact_summary,
                update_section_summary,
            )
            from pathly_orchestrator.runner.inference import summarize_content

            conn = get_db()
            row = conn.execute(
                "SELECT path, type FROM comms_artifacts WHERE id=?",
                (artifact_id,),
            ).fetchone()
            if row is None:
                return
            path = row["path"]
            artifact_type = row["type"] or "md"

            if not _is_md(path):
                return

            text = _read_file_text(path)
            if text is None:
                return

            # Whole-artifact topic-map summary
            result = summarize_content(text, artifact_type=artifact_type, backend=backend)
            if result.summary is not None:
                update_artifact_summary(conn, artifact_id, result.summary)

            # Per-section summaries (≤1 sentence each)
            sections = get_artifact_sections(conn, artifact_id)
            if not sections:
                return

            file_lines = text.splitlines(keepends=True)
            for sec in sections:
                ls = max(1, sec["line_start"]) - 1
                le = min(len(file_lines), sec["line_end"])
                sec_text = "".join(file_lines[ls:le])
                if not sec_text.strip():
                    continue
                sec_result = summarize_content(sec_text, artifact_type=artifact_type, max_sentences=1, backend=backend)
                if sec_result.summary is not None:
                    update_section_summary(conn, sec["id"], sec_result.summary)

        except Exception:
            logger.debug("_schedule_resummarize_async failed for %s", artifact_id, exc_info=True)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


def hydrate_section(
    conn,
    *,
    artifact_id: str | None = None,
    scope: str = "",
    artifact: str = "",
    anchor: str | None = None,
    project_root: str | None = None,
) -> dict:
    """Hydrate a section of a .md artifact.  Returns {body: {...}, status: int}.

    Resolves the artifact row (by id OR by scope+artifact basename), enforces the
    path-traversal guard (§4.3), ensures the index, slices the file, and builds the
    §4.2 response body.  Never raises — unexpected errors become {status:500}.

    Path-traversal guard: artifact basename must not contain a path separator;
    the resolved absolute path must be under pathly/plans/<scope>/.
    """
    try:
        from pathly_orchestrator.db.queries.comms import (
            find_or_create_artifact_by_path,
            get_artifact_sections,
            get_section,
        )

        # ── Resolve artifact row ────────────────────────────────────────────
        if artifact_id:
            row = conn.execute(
                "SELECT a.*, m.scope AS msg_scope FROM comms_artifacts a "
                "JOIN comms_messages m ON m.id = a.message_id "
                "WHERE a.id=?",
                (artifact_id,),
            ).fetchone()
            if row is None:
                return {
                    "body": {"error": "artifact_not_found", "artifact_id": artifact_id},
                    "status": 404,
                }
            row = dict(row)
            path = row["path"]
            resolved_scope = scope or row.get("msg_scope", "")
        else:
            if not scope or not artifact:
                return {
                    "body": {"error": "specify artifact_id or scope+artifact"},
                    "status": 400,
                }

            # ── Path-traversal guard (§4.3) ───────────────────────────────
            safe = safe_plan_path(scope, artifact, project_root)
            if safe is None:
                return {
                    "body": {"error": "path_out_of_scope",
                             "detail": "scope or artifact fails traversal check"},
                    "status": 400,
                }

            path = safe
            resolved_scope = scope

            db_row = find_or_create_artifact_by_path(conn, resolved_scope, path)
            if db_row is None:
                return {
                    "body": {"error": "artifact_not_found", "path": path},
                    "status": 404,
                }
            artifact_id = db_row["id"]
            row = db_row

        # ── Non-.md early return ──────────────────────────────────────────
        if not _is_md(path):
            if anchor:
                return {
                    "body": {"error": "anchor required",
                             "detail": "section anchoring is .md-only (§8)"},
                    "status": 400,
                }
            text = _read_file_text(path)
            if text is None:
                return {
                    "body": {"error": "artifact_not_found", "path": path},
                    "status": 404,
                }
            return {
                "body": {
                    "ok": True,
                    "artifact_id": artifact_id,
                    "artifact": os.path.basename(path),
                    "anchor": None,
                    "heading": None,
                    "line_start": 1,
                    "line_end": len(text.splitlines()),
                    "text": text,
                    "summary": row.get("summary"),
                    "stale_rebuilt": False,
                },
                "status": 200,
            }

        # ── Whole-file request (anchor=None) ──────────────────────────────
        if anchor is None:
            text = _read_file_text(path)
            if text is None:
                return {
                    "body": {"error": "artifact_not_found", "path": path},
                    "status": 404,
                }
            return {
                "body": {
                    "ok": True,
                    "artifact_id": artifact_id,
                    "artifact": os.path.basename(path),
                    "anchor": None,
                    "heading": None,
                    "line_start": 1,
                    "line_end": len(text.splitlines()),
                    "text": text,
                    "summary": row.get("summary"),
                    "stale_rebuilt": False,
                },
                "status": 200,
            }

        # ── Ensure index is fresh (§3.4) ──────────────────────────────────
        ensure_result = ensure_indexed(conn, resolved_scope, path, project_root)
        stale_rebuilt = ensure_result.get("stale_rebuilt", False)

        if not ensure_result.get("ok"):
            err = ensure_result.get("error", "stale_index")
            if err == "artifact_not_found":
                return {
                    "body": {"error": "artifact_not_found", "path": path},
                    "status": 404,
                }
            return {
                "body": {"error": err, "detail": ensure_result.get("detail", "")},
                "status": 409,
            }

        # ── Fetch section row ─────────────────────────────────────────────
        # artifact_id is always resolved above (by-id or by-path sets it),
        # but narrow explicitly so static analysers (Pyright) see str not str|None.
        if not artifact_id:
            return {
                "body": {"error": "artifact_not_found"},
                "status": 404,
            }
        sec_row = get_section(conn, artifact_id, anchor)
        if sec_row is None:
            available = [s["anchor"] for s in get_artifact_sections(conn, artifact_id)]
            return {
                "body": {
                    "error": "anchor_not_found",
                    "anchor": anchor,
                    "available": available,
                },
                "status": 404,
            }

        # ── Slice the file ────────────────────────────────────────────────
        text_full = _read_file_text(path)
        if text_full is None:
            return {
                "body": {"error": "stale_index", "detail": f"cannot read {path}"},
                "status": 409,
            }

        file_lines = text_full.splitlines(keepends=True)
        line_start = sec_row["line_start"]
        line_end = sec_row["line_end"]
        # line_start/line_end are 1-based inclusive; clamp defensively
        ls = max(1, line_start) - 1
        le = min(len(file_lines), line_end)
        section_text = "".join(file_lines[ls:le])

        return {
            "body": {
                "ok": True,
                "artifact_id": artifact_id,
                "artifact": os.path.basename(path),
                "anchor": anchor,
                "heading": sec_row.get("heading"),
                "line_start": line_start,
                "line_end": line_end,
                "text": section_text,
                "summary": sec_row.get("summary"),
                "stale_rebuilt": stale_rebuilt,
            },
            "status": 200,
        }

    except Exception as exc:
        logger.exception("hydrate_section error")
        return {
            "body": {"error": str(exc), "type": type(exc).__name__},
            "status": 500,
        }


def index_artifact_async(
    artifact_id: str, path: str, scope: str = "", backend: str | None = None
) -> None:
    """Daemon-thread eager indexer, mirrors embed_async.

    Parses sections and writes the index for path. .md ONLY (§8 item 0) —
    early-returns for non-.md before parsing. Best-effort: never raises to caller.

    `backend` is the per-upload summary-backend override (None ⇒ global app-setting),
    used when this index triggers a (re)summarize.
    """
    if not _is_md(path):
        return

    def _worker() -> None:
        try:
            from pathly_orchestrator.db.connection import get_db
            from pathly_orchestrator.db.queries.comms import reindex_artifact_sections
            from pathly_orchestrator.runner.sections import (
                file_fingerprint,
                parse_sections,
                structure_key as compute_structure_key,
            )

            if not os.path.exists(path):
                return

            conn = get_db()

            existing = conn.execute(
                "SELECT indexed_hash, indexed_structure_key FROM comms_artifacts WHERE id=?",
                (artifact_id,),
            ).fetchone()

            try:
                cur_mtime, cur_hash = file_fingerprint(path)
            except OSError:
                return

            if existing and existing["indexed_hash"] == cur_hash:
                return

            text = _read_file_text(path)
            if text is None:
                return

            sections = parse_sections(text)
            cur_struct = compute_structure_key(sections)

            section_dicts = [
                {
                    "id": str(uuid.uuid4()),
                    "anchor": sec.anchor,
                    "heading": sec.heading,
                    "line_start": sec.line_start,
                    "line_end": sec.line_end,
                    "ordinal": sec.ordinal,
                }
                for sec in sections
            ]

            old_struct = existing["indexed_structure_key"] if existing else None
            reindex_artifact_sections(
                conn, artifact_id, section_dicts, cur_mtime, cur_hash, cur_struct
            )

            # Summarize on FIRST index (old_struct is None) or a structural change.
            # No-op when the effective backend is minilm/off (summarize returns None),
            # so the default stays behavior-identical; with a backend on, new uploads
            # and agent-created .md actually get summarized.
            if old_struct is None or cur_struct != old_struct:
                _schedule_resummarize_async(artifact_id, backend=backend)

        except Exception:
            logger.debug("index_artifact_async failed for %s", path, exc_info=True)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
