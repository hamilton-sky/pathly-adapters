#!/usr/bin/env python3
"""P2 (board-scoped-storage): inventory dry-run.

Shared-bucket folders  pathly/{debugs,explorations,fixes}/<slug>/  predate the
board-scoped layout. This finds each one, infers WHICH board it belongs to
(grounded in the DB where possible, slug-match otherwise), computes the new
board-scoped path, and counts every DB reference that would repath.

Board-scoped target:
    board == feature  ->  pathly/features/<scope>/<kind>/<slug>/
    board == project  ->  pathly/project/<kind>/<slug>/
  where <kind> is the bucket name (debugs/explorations/fixes).

Board-inference, strongest signal first:
  1. GROUNDED-msg   : a comms_messages row whose artifact_path/context_refs point
                      INTO this folder -> use that row's (board, scope).
  2. GROUNDED-art   : a comms_artifacts.path points into this folder -> join to its
                      message -> (board, scope).
  3. SLUG-MATCH     : folder slug equals a pathly/features/<name> dir -> feature board.
  4. DEFAULT-project: nothing references it -> project board (the agreed default).

DB refs counted (would repath old-prefix -> new-prefix):
  - comms_artifacts.path
  - comms_messages.artifact_path
  - comms_messages.context_refs (JSON 'artifact' fields)
NOT touched: comms_messages.text (free-form narrative) -> reported as a count only.

READ-ONLY. There is no write path here on purpose; apply is a separate reviewed step.
"""
from __future__ import annotations

import os
import sqlite3
import sys
from collections import Counter, defaultdict

_reconf = getattr(sys.stdout, "reconfigure", None)  # Windows cp1252 chokes on box chars
if _reconf:
    try:
        _reconf(encoding="utf-8")
    except Exception:
        pass

BUCKETS = ("debugs", "explorations", "fixes")
DB = os.path.expanduser("~/.pathly/pathly.db")
ROOT = os.getcwd().replace("\\", "/").rstrip("/")


def norm(p: str) -> str:
    return (p or "").replace("\\", "/")


def rel_key(bucket: str, slug: str) -> str:
    """The path substring that identifies refs into this folder, slash-normalized."""
    return f"pathly/{bucket}/{slug}"


def list_feature_dirs() -> set[str]:
    fdir = os.path.join(ROOT, "pathly", "features")
    if not os.path.isdir(fdir):
        return set()
    return {d for d in os.listdir(fdir) if os.path.isdir(os.path.join(fdir, d))}


def find_folders() -> list[tuple[str, str]]:
    """Return [(bucket, slug), ...] for every shared-bucket folder on disk."""
    out = []
    for bucket in BUCKETS:
        bdir = os.path.join(ROOT, "pathly", bucket)
        if not os.path.isdir(bdir):
            continue
        for slug in sorted(os.listdir(bdir)):
            if os.path.isdir(os.path.join(bdir, slug)):
                out.append((bucket, slug))
    return out


def collect_refs(con: sqlite3.Connection):
    """Pull every DB row that could reference a shared-bucket path, once.
    Returns dicts keyed by rel-substring is impractical (paths vary), so we keep
    raw rows and match per-folder in Python."""
    msgs = con.execute(
        "SELECT id, board, scope, slug, goal_id, type, artifact_path, context_refs, text "
        "FROM comms_messages WHERE deleted_at IS NULL"
    ).fetchall()
    arts = con.execute(
        "SELECT a.id AS aid, a.path AS path, a.message_id AS mid, "
        "m.board AS board, m.scope AS scope "
        "FROM comms_artifacts a LEFT JOIN comms_messages m ON a.message_id = m.id"
    ).fetchall()
    return msgs, arts


def infer_board(bucket, slug, msgs, arts, feature_dirs):
    """Return (board, scope, source, confidence, evidence)."""
    key = rel_key(bucket, slug)
    votes = Counter()            # (board, scope) -> count
    evidence = defaultdict(int)  # source -> hits

    for m in msgs:
        hit = False
        if key in norm(m["artifact_path"]):
            hit = True
            evidence["artifact_path"] += 1
        cr = norm(m["context_refs"])
        if key in cr:
            hit = True
            evidence["context_refs"] += 1
        if hit and (m["board"] or m["scope"]):
            votes[(m["board"], m["scope"])] += 1

    for a in arts:
        if key in norm(a["path"]) and (a["board"] or a["scope"]):
            votes[(a["board"], a["scope"])] += 1
            evidence["artifact.path"] += 1

    if votes:
        board, scope = votes.most_common(1)[0][0]
        conf = "grounded" if len(votes) == 1 else "grounded-ambiguous"
        return board, scope, f"db({','.join(sorted(evidence))})", conf, dict(votes)

    # No DB grounding -> slug heuristics
    if slug in feature_dirs:
        return "feature", slug, "slug-match-feature", "inferred", {}
    return "project", None, "default-project", "default", {}


def new_path(board, scope, bucket, slug) -> str:
    if board == "feature" and scope:
        return f"pathly/features/{scope}/{bucket}/{slug}"
    return f"pathly/project/{bucket}/{slug}"


def count_repaths(old_key, msgs, arts):
    """How many DB refs contain old_key (would repath). Returns dict + text count."""
    c = Counter()
    for m in msgs:
        if old_key in norm(m["artifact_path"]):
            c["artifact_path"] += 1
        if old_key in norm(m["context_refs"]):
            c["context_refs"] += 1
        if old_key in norm(m["text"]):
            c["text(narrative,untouched)"] += 1
    for a in arts:
        if old_key in norm(a["path"]):
            c["artifacts.path"] += 1
    return c


def main():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    feature_dirs = list_feature_dirs()
    folders = find_folders()
    msgs, arts = collect_refs(con)

    print(f"DB    : {DB}")
    print(f"root  : {ROOT}")
    print(f"mode  : DRY-RUN (read-only)\n")
    print(f"Shared-bucket folders found: {len(folders)}")
    print(f"Feature dirs (for slug-match): {len(feature_dirs)}\n")

    grand = Counter()
    src_tally = Counter()
    plan = []

    for bucket, slug in folders:
        board, scope, source, conf, votes = infer_board(bucket, slug, msgs, arts, feature_dirs)
        old = rel_key(bucket, slug)
        new = new_path(board, scope, bucket, slug)
        repaths = count_repaths(old, msgs, arts)
        src_tally[conf] += 1
        for k, v in repaths.items():
            grand[k] += v
        plan.append((bucket, slug, old, new, source, conf, votes, repaths))

    # ── per-folder plan ──
    for bucket, slug, old, new, source, conf, votes, repaths in plan:
        print(f"── {old}")
        print(f"     ->  {new}")
        print(f"     board-inference: {source}  [{conf}]")
        if votes:
            vs = "; ".join(f"board={b or '-'},scope={s or '-'}×{n}" for (b, s), n in votes.items())
            print(f"     db votes: {vs}")
        actionable = {k: v for k, v in repaths.items() if "untouched" not in k}
        untouched = {k: v for k, v in repaths.items() if "untouched" in k}
        print(f"     DB refs to repath: {sum(actionable.values())}  {dict(actionable) or ''}")
        if untouched:
            print(f"     narrative mentions (left as-is): {sum(untouched.values())}")
        print()

    # ── summary ──
    print("=" * 60)
    print("SUMMARY")
    print(f"  folders to move          : {len(folders)}")
    for k in sorted(src_tally):
        print(f"    {k:20}: {src_tally[k]}")
    actionable_total = sum(v for k, v in grand.items() if "untouched" not in k)
    print(f"  DB refs to repath (total): {actionable_total}")
    for k in sorted(grand):
        tag = "  (UNTOUCHED)" if "untouched" in k else ""
        print(f"    {k:28}: {grand[k]}{tag}")
    con.close()


if __name__ == "__main__":
    main()
