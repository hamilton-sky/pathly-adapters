"""Benchmark /comms/search retrieval against a real board.

For each of 20 search-style queries it shows, side by side:
  • keyword (BM25/FTS5) arm  — what search_by_keyword retrieves
  • semantic (cosine) arm    — what search_by_embedding retrieves, with raw distances
                               (+ = within the 0.72 floor, - = would be dropped)
  • hybrid reconciliation    — what search_by_hybrid returns: RRF-fused, semantic
                               floored at 0.72, each row tagged [kw] or [se <dist>]
                               (keyword hits bypass the floor)
and an automated PASS/FAIL check of the invariants:
  - nonsense queries return NOTHING (floor works, no recency padding)
  - every semantic-tagged hybrid row is within the floor
  - every keyword-tagged hybrid row really came from the BM25 arm
  - queries with a literal/stemmed term surface a keyword hit

Run:  PYTHONPATH=src python scripts/search_benchmark.py [board] [scope]
Exit code 0 iff every query behaved as expected.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pathly_orchestrator.db.connection import get_db  # noqa: E402
from pathly_orchestrator.db.queries.comms_embeddings import (  # noqa: E402
    SEMANTIC_DISTANCE_CEILING as FLOOR,
    search_by_embedding,
    search_by_hybrid,
    search_by_keyword,
)
from pathly_orchestrator.runner.embeddings import embed  # noqa: E402

BOARD = sys.argv[1] if len(sys.argv) > 1 else "feature"
SCOPE = sys.argv[2] if len(sys.argv) > 2 else "planner-hierarchy"

# (query, category, expectation)
#   keyword  -> hybrid must contain >=1 keyword-tagged row (literal/stemmed term present)
#   any      -> hybrid must be non-empty (meaning-based match acceptable)
#   empty    -> hybrid must be empty (nothing is genuinely relevant)
#   edge     -> floor-boundary demo: the outcome is NOT asserted (only the floor +
#               BM25-membership invariants are), so the row documents where the 0.72
#               cutoff lands — a loose paraphrase dropped, a gibberish token that
#               slips just under it — without codifying either as "correct". Read the
#               distances. Stays green if a future floor change moves the boundary.
QUERIES = [
    ("prd-import", "exact", "keyword"),
    ("BOARD_EVAL", "exact", "keyword"),
    ("review pass", "exact", "keyword"),
    ("acceptance criteria", "exact", "keyword"),
    ("warning", "exact", "keyword"),
    ("reviewing", "stemmed", "keyword"),
    ("tested", "stemmed", "keyword"),
    ("seeded", "stemmed", "keyword"),
    ("did the tests pass", "semantic", "any"),
    ("what lessons were learned", "semantic", "any"),
    ("code that hardcodes a value", "floor-edge", "edge"),
    ("how is the board evaluated", "semantic", "any"),
    ("prd:import", "operator", "keyword"),
    ("ArtifactsView.tsx", "operator", "keyword"),
    ("(deferred)", "operator", "keyword"),
    ("xylophone quantum banana", "nonsense", "empty"),
    ("zzznonsense12345", "floor-edge", "edge"),
    ("goal run finished", "multiword", "keyword"),
    ("future work deferred", "multiword", "keyword"),
    ("modernize prd", "multiword", "any"),
]


def snip(row: dict, n: int = 40) -> str:
    t = (row.get("text", "") or "").replace("\n", " ")
    return t.encode("ascii", "replace").decode()[:n]


def kw_line(rows: list[dict]) -> str:
    return " | ".join(snip(r, 34) for r in rows[:3]) or "-"


def sem_line(rows: list[dict]) -> str:
    out = []
    for r in rows[:3]:
        d = r.get("_distance", 9.0)
        out.append(f"{'+' if d <= FLOOR else '-'}{d:.2f} {snip(r, 30)}")
    return " | ".join(out) or "-"


def hyb_line(rows: list[dict]) -> str:
    if not rows:
        return "(empty)"
    out = []
    for r in rows[:3]:
        tag = "kw    " if r.get("_match_source") == "keyword" else f"se{r.get('_distance', 0):.2f}"
        out.append(f"[{tag}] {snip(r, 30)}")
    return " | ".join(out)


def check(exp: str, kw_ids: set, hyb: list) -> list[str]:
    problems: list[str] = []
    if exp == "empty" and hyb:
        problems.append(f"expected empty, got {len(hyb)}")
    if exp == "any" and not hyb:
        problems.append("expected >=1 hit, got 0")
    if exp == "keyword" and not any(r.get("_match_source") == "keyword" for r in hyb):
        problems.append("expected a keyword hit")
    for r in hyb:
        if r.get("_match_source") == "semantic" and r.get("_distance", 9.0) > FLOOR:
            problems.append(f"semantic row past floor ({r['_distance']:.2f})")
        if r.get("_match_source") == "keyword" and r["id"] not in kw_ids:
            problems.append("keyword-tagged row not in BM25 set")
    return problems


def main() -> int:
    conn = get_db()
    if embed("warm up the model") is None:
        print("!! embedding model unavailable — semantic arm is inert")
    print(f"Board {BOARD}/{SCOPE}   floor={FLOOR}   ({len(QUERIES)} queries)")
    print("=" * 96)
    npass = 0
    for i, (q, cat, exp) in enumerate(QUERIES, 1):
        e = embed(q)
        kw = search_by_keyword(conn, q, [BOARD], [SCOPE], 5)
        # Membership set for the check must match hybrid's internal BM25 fetch (k*2),
        # else a legit keyword hit ranked 6-10 looks like it "isn't in the BM25 set".
        kw_ids = {r["id"] for r in search_by_keyword(conn, q, [BOARD], [SCOPE], 10)}
        sem = search_by_embedding(conn, e, [BOARD], [SCOPE], 5, max_distance=None) if e else []
        hyb = search_by_hybrid(conn, q, e, [BOARD], [SCOPE], 5, max_distance=FLOOR)
        problems = check(exp, kw_ids, hyb)
        ok = not problems
        npass += ok
        sem_in = sum(1 for r in sem if r.get("_distance", 9.0) <= FLOOR)
        h_kw = sum(1 for r in hyb if r.get("_match_source") == "keyword")
        verdict = "PASS" if ok else "FAIL: " + "; ".join(problems)
        print(f"\n[Q{i:02}] {q!r:30} {cat:9} expect={exp:8} {verdict}")
        print(f"      kw={len(kw)}  sem<=floor={sem_in}/{len(sem)}  ->  hybrid={len(hyb)} (kw:{h_kw} se:{len(hyb)-h_kw})")
        print(f"      keyword : {kw_line(kw)}")
        print(f"      semantic: {sem_line(sem)}")
        print(f"      hybrid  : {hyb_line(hyb)}")
    print("\n" + "=" * 96)
    print(f"RESULT: {npass}/{len(QUERIES)} queries behaved as expected")
    return 0 if npass == len(QUERIES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
