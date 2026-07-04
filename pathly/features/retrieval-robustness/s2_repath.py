#!/usr/bin/env python3
"""S2 (retrieval-robustness): repath stale `pathly/plans/` -> `pathly/features/`
references in the comms board DB, on real data.

Only repaths a reference when the file has ACTUALLY MOVED to features/ (the features/
path exists on disk). References whose file is still physically at plans/ are LEFT
untouched — they still resolve, so touching them would be churn/risk. References where
NEITHER location exists are already-broken (404 today); they are repathed to features/
as a best-effort (that is the canonical home now) and reported separately so you can see
them.

Columns handled (all point at feature-workspace files, all 404 on hydrate when stale):
  - comms_artifacts.path         (the artifact's on-disk path)
  - comms_messages.artifact_path (an artifact-type message's own path)
  - comms_messages.context_refs  (JSON: [{"artifact": "...", "anchor": ...}, ...])

NOT touched: comms_messages.text — free-form narrative; repathing prose is out of S2
scope and risks corrupting sentences. Reported as a count only.

Dry-run by default. --apply backs the DB up first and runs inside one transaction.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import time
from collections import Counter

PLANS = "pathly/plans/"
FEATS = "pathly/features/"


def _abs(path: str, root: str) -> str:
    p = path.replace("\\", "/")
    # Windows absolute (C:/...) or POSIX absolute
    if os.path.isabs(p) or (len(p) > 1 and p[1] == ":"):
        return p
    return os.path.join(root, p).replace("\\", "/")


def classify(path: str, root: str):
    """Return (decision, new_path). decision ∈ {moved, stay, broken, n/a}."""
    if PLANS not in path:
        return ("n/a", path)
    new_path = path.replace(PLANS, FEATS, 1)
    feats_exists = os.path.exists(_abs(new_path, root))
    plans_exists = os.path.exists(_abs(path, root))
    if feats_exists:
        return ("moved", new_path)      # file is at features/ -> repath
    if plans_exists:
        return ("stay", path)           # still at plans/ -> leave as-is
    return ("broken", new_path)         # neither exists -> best-effort repath, flagged


def repath_refs_json(raw: str, root: str):
    """Repath the 'artifact' field of each context_refs element. Returns (new_raw, changes)
    where changes is a list of (old, new, decision) for the plans/ entries."""
    try:
        refs = json.loads(raw)
    except Exception:
        return (raw, [])
    if not isinstance(refs, list):
        return (raw, [])
    changes = []
    changed = False
    for el in refs:
        if not isinstance(el, dict):
            continue
        art = el.get("artifact")
        if isinstance(art, str) and PLANS in art:
            decision, new = classify(art, root)
            changes.append((art, new, decision))
            if decision in ("moved", "broken") and new != art:
                el["artifact"] = new
                changed = True
    return (json.dumps(refs) if changed else raw, changes)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.expanduser("~/.pathly/pathly.db"))
    ap.add_argument("--root", default=os.getcwd(),
                    help="project root for existence checks (default: cwd)")
    ap.add_argument("--apply", action="store_true", help="write changes (backs DB up first)")
    ap.add_argument("--limit-samples", type=int, default=8)
    args = ap.parse_args()

    root = args.root.replace("\\", "/").rstrip("/")
    con = sqlite3.connect(args.db)
    con.row_factory = sqlite3.Row

    tally = Counter()
    plan_moved, plan_stay, plan_broken = [], [], []   # (table, id, old, new)
    updates = []  # (sql, params)

    # 1 + 2: single-path columns
    for table, idcol, col in (
        ("comms_artifacts", "id", "path"),
        ("comms_messages", "id", "artifact_path"),
    ):
        rows = con.execute(
            f"SELECT {idcol} AS id, {col} AS val FROM {table} WHERE {col} LIKE ?",
            (f"%{PLANS}%",),
        ).fetchall()
        for r in rows:
            decision, new = classify(r["val"], root)
            tally[f"{col}:{decision}"] += 1
            rec = (table, r["id"], r["val"], new)
            if decision == "moved":
                plan_moved.append(rec)
            elif decision == "stay":
                plan_stay.append(rec)
            elif decision == "broken":
                plan_broken.append(rec)
            if decision in ("moved", "broken") and new != r["val"]:
                updates.append(
                    (f"UPDATE {table} SET {col}=? WHERE {idcol}=?", (new, r["id"]))
                )

    # 3: context_refs JSON
    rows = con.execute(
        "SELECT id, context_refs FROM comms_messages WHERE context_refs LIKE ?",
        (f"%{PLANS}%",),
    ).fetchall()
    for r in rows:
        new_raw, changes = repath_refs_json(r["context_refs"], root)
        for old, new, decision in changes:
            tally[f"context_refs:{decision}"] += 1
            rec = ("comms_messages.context_refs", r["id"], old, new)
            if decision == "moved":
                plan_moved.append(rec)
            elif decision == "stay":
                plan_stay.append(rec)
            elif decision == "broken":
                plan_broken.append(rec)
        if new_raw != r["context_refs"]:
            updates.append(
                ("UPDATE comms_messages SET context_refs=? WHERE id=?", (new_raw, r["id"]))
            )

    text_ct = con.execute(
        "SELECT COUNT(*) FROM comms_messages WHERE text LIKE ? AND deleted_at IS NULL",
        (f"%{PLANS}%",),
    ).fetchone()[0]

    # ── Report ────────────────────────────────────────────────────────────────
    print(f"DB   : {args.db}")
    print(f"root : {root}")
    print(f"mode : {'APPLY' if args.apply else 'DRY-RUN'}\n")
    print("Per-column classification (moved=repath, stay=leave, broken=repath best-effort):")
    for k in sorted(tally):
        print(f"  {k:32} {tally[k]}")
    print(f"\n  MOVED  (will repath)      : {len(plan_moved)}")
    print(f"  STAY   (file still at plans/): {len(plan_stay)}")
    print(f"  BROKEN (neither on disk)  : {len(plan_broken)}  -> repathed to features/ best-effort")
    print(f"  text mentions (untouched) : {text_ct}")
    print(f"  total UPDATE statements   : {len(updates)}")

    def _dump(label, recs):
        print(f"\n── {label} (showing up to {args.limit_samples}) ──")
        for table, rid, old, new in recs[: args.limit_samples]:
            sid = rid[:8] if isinstance(rid, str) else rid
            if old == new:
                print(f"  [{table} {sid}] STAY  {old}")
            else:
                print(f"  [{table} {sid}]\n      - {old}\n      + {new}")

    _dump("MOVED -> repath", plan_moved)
    _dump("STAY -> unchanged", plan_stay)
    _dump("BROKEN -> best-effort repath (still 404 until the file is restored)", plan_broken)

    if args.apply:
        backup = args.db + f".bak-s2-{int(time.time())}"
        shutil.copy2(args.db, backup)
        print(f"\n[apply] DB backed up -> {backup}")
        try:
            con.execute("BEGIN")
            for sql, params in updates:
                con.execute(sql, params)
            con.commit()
            print(f"[apply] committed {len(updates)} update(s).")
        except Exception as exc:
            con.rollback()
            print(f"[apply] ROLLED BACK on error: {exc}")
            raise
    else:
        print("\n(dry-run — no changes written. Re-run with --apply to execute.)")

    con.close()


if __name__ == "__main__":
    main()
