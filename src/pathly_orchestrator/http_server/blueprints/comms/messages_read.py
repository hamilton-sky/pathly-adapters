"""Read-only message board endpoints — GET /comms and POST /comms/search.

Split out of ``messages_crud.py`` (which holds the writers: acknowledge, answer, edit, delete,
supersede, trash, restore). Neither route here writes anything.
"""

from __future__ import annotations

import logging

from flask import jsonify, request

from ._messages_bp import bp
from ._helpers import read_json_body


@bp.route("/comms", methods=["GET"])
def comms_get():
    """Fetch messages for a feature board."""
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.comms import get_messages as _get_messages

        feature = request.args.get("feature", "").strip()
        if not feature:
            return jsonify({"error": "Query parameter 'feature' is required"}), 400

        board = (request.args.get("board") or "feature").strip() or "feature"
        if board not in ("feature", "project", "global"):
            board = "feature"
        scope = (request.args.get("scope") or feature).strip() or feature
        msg_type = request.args.get("type") or None
        status = request.args.get("status") or None
        try:
            limit = int(request.args.get("limit", "50"))
        except ValueError:
            limit = 50

        conn = _get_db()
        messages = _get_messages(
            conn,
            board=board,
            scope=scope,
            type=msg_type,
            status=status,
            limit=limit,
            # Board feed: never let run churn evict the (bounded) goals/tasks out of the
            # newest-`limit` window — the Goals & Tasks view needs them all, and the Messages
            # thread filters them out anyway. Only applies when not filtering by an explicit type.
            include_structural=(msg_type is None),
        )
        return jsonify(messages), 200
    except Exception as exc:
        logging.exception("comms_get error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


# Bounds for /comms/search hardening: a search box never needs a multi-KB query
# (which would hog the process-wide embedding-model lock) or hundreds of results.
_MAX_QUERY_LEN = 512
_MAX_K = 50


@bp.route("/comms/search", methods=["POST"])
def comms_search():
    """Hybrid (BM25 + semantic) search across boards.

    Semantic hits are floored at SEMANTIC_DISTANCE_CEILING; keyword hits bypass the
    floor. A query matching nothing returns [] — results are never padded with
    recent messages (that padding made every query "match" the newest rows).
    """
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db
        from pathly_orchestrator.db.queries.comms import search_by_embedding as _search
        from pathly_orchestrator.db.queries.comms import (
            search_by_hybrid as _search_hybrid,
        )
        from pathly_orchestrator.db.queries.comms import (
            search_by_keyword as _search_keyword,
        )
        from pathly_orchestrator.db.queries.comms_embeddings import (
            SEMANTIC_DISTANCE_CEILING as _CEILING,
        )
        from pathly_orchestrator.runner.embeddings import embed as _embed

        # silent=True → a malformed/empty body yields None (a clean 400), not a
        # werkzeug BadRequest bubbling into the generic 500 that echoes exception text.
        data = read_json_body()
        if not isinstance(data, dict):
            return jsonify({"error": "Missing or malformed JSON body"}), 400

        query = data.get("query", "")
        feature = data.get("feature", "")
        if not isinstance(query, str) or not query.strip():
            return jsonify({"error": "Field 'query' must be a non-empty string"}), 400
        if not isinstance(feature, str) or not feature.strip():
            return jsonify({"error": "Field 'feature' must be a non-empty string"}), 400
        # Cap length before embedding: a multi-KB query is never a real search and
        # would hold the process-wide model lock, stalling every other embed.
        query = query[:_MAX_QUERY_LEN]

        board = data.get("board", "feature")
        if board not in ("feature", "project", "global"):
            board = "feature"
        scope = data.get("scope") or feature
        # bool is an int subclass — reject it so k=true can't silently become LIMIT 1.
        k = data.get("k", 5)
        if not isinstance(k, int) or isinstance(k, bool) or k <= 0:
            k = 5
        k = min(k, _MAX_K)

        mode = data.get("mode", "hybrid")
        if mode not in ("hybrid", "semantic", "keyword"):
            mode = "hybrid"

        # Only the semantic/hybrid arms need a query vector — keyword mode skips the
        # model forward-pass entirely.
        embedding = _embed(query) if mode != "keyword" else None
        conn = _get_db()

        if mode == "keyword":
            results = _search_keyword(conn, query, [board], [scope], k)
        elif mode == "semantic":
            if embedding is not None:
                results = _search(
                    conn,
                    embedding=embedding,
                    boards=[board],
                    scopes=[scope],
                    k=k,
                    max_distance=_CEILING,
                )
            else:
                # No embedding model → degrade to keyword matching, which is still
                # honest; recency rows are not matches.
                results = _search_keyword(conn, query, [board], [scope], k)
        else:
            results = _search_hybrid(
                conn, query, embedding, [board], [scope], k, max_distance=_CEILING
            )

        return jsonify(results), 200
    except Exception as exc:
        logging.exception("comms_search error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500
