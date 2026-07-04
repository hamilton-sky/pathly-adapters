# SPEC — Retrieval Robustness

_Follow-up to the context-retrieval-quality work (CT1–CT6, merged `ea77955d`). Every
finding below was verified by a 20-agent multi-probe pass (code read + independent live
probe against the real `~/.pathly/pathly.db`); all 14 load-bearing claims confirmed, none
refuted. This spec turns the architectural assessment into scoped, buildable work._

> **Relationship to [`production-readiness-plan`](../production-readiness-plan/SPEC.md).** That spec is
> the whole-system hardening roadmap (thesis: _consolidation > expansion_; trust ONE loop first). This
> one is a **subsystem deep-dive that sits under it**, not a competing plan. Two explicit links:
> **S2 (repath stale `context_refs`) folds into its G2 / Phase 2** — the incomplete
> `pathly/plans/` → `pathly/features/` storage migration; same root cause, so do them together rather
> than twice. **S1 (loud degradation)** is a retrieval-specific instance of its **Phase 5** ("make
> failures observable — currently silent by design"); the CT6 `/health` work already merged is the
> shared down payment. Everything else here (S3–S6) is additive and lives only in this spec. Per
> production-readiness's "trust the core first" ordering, **S1 + S2 align with its P0**; S3–S6 are
> refinements that can wait behind the golden-path gate.

---

## A. How the retrieval system works (verified)

Every agent prompt gets a `## Communication Board` block from `retrieve_board_context()`.

- **Hybrid search** (`search_by_hybrid`, comms_embeddings.py:122-165): runs **BM25** (FTS5
  `ORDER BY rank`, `search_by_keyword`) **and vector cosine** (sqlite-vec `vec_distance_cosine`
  over all-MiniLM-L6-v2, `search_by_embedding`) and merges them via **Reciprocal Rank Fusion**
  (`score = 1/(60+bm25_rank) + 1/(60+sem_rank)`, `_RRF_K=60`). Cosine `_distance` is re-attached
  only from the semantic side, so keyword-only rows carry `_distance=None`.
- **Two relevance gates** (comms_context.py:151-167): per-tier distance cutoff
  `{feature 0.75, project 0.55, global 0.50}` for scored rows; the CT4 keyword bound drops
  unscored cross-tier rows when a task embedding exists.
- **Governance** (comms_messages.py:157-195): pending decisions + open escalations pulled by
  plain `WHERE`-clause SQL (no ranking, no distance), injected first and unconditionally, and
  excluded from the semantic channel via `_is_context()` so nothing double-renders.
- **Four channels, fixed order**: Governance → Referenced (context_refs → hydrated authoritative
  text) → Context/Auto-derived (semantic) → Catalog (≤12 pull-on-demand pointers).
- **Graceful degradation**: vec down → recency; FTS down → semantic-only; both empty → `[]`.

**Strengths (keep):** the RRF hybrid is correct and well-tested; the trust-tiered channel model
(deterministic governance / authoritative refs / advisory semantic / pull catalog) is a genuinely
strong information architecture for LLM context.

---

## B. Assessment — the load-bearing weakness

The algorithm layer is sound; the **operational layer is fragile**. A single recurring
anti-pattern appears three times: **a critical capability gated by one silently-latched boolean,
with a silent no-op fallback** — so the system keeps returning *something* while a headline
feature is fully off. The system prefers **fail-silent** over **fail-loud**.

- **Embeddings-dark** (the CT6 root cause): one process-global `_VEC_AVAILABLE`, set once, that
  silently disabled all embedding writes + vector search. Fixed for the server path, but the
  verification agents still had to force the flag True in a bare interpreter — the fragility
  (one boolean, set-once, silent) remains the foundation.
- **FTS silent-omission** (newly reproduced): `comms_fts` is external-content, synced only by
  triggers, with no rebuild/backfill. An agent reproduced permanent, error-free omission by
  inserting rows before the triggers exist. Latent today (integrity-check passes).
- **Stale authoritative refs**: 4 of 5 context_refs currently on the board point at legacy
  `pathly/plans/…` paths that no longer exist and fail to hydrate — the "authoritative" channel
  is partly broken on real data even after the CT5 resolver fix.

Plus two design gaps: the **Referenced channel is unbounded** (one hydrated artifact added
13.6 K chars in the probe while Context is capped at 2000), and **`comms_chunk_embeddings` is
empty** (the subtopic-rescue merge is built + functional but dormant).

**Through-line fix:** make degradation loud and prefer *verify-then-use* over *set-once-latch*.

---

## C. Solutions (buildable)

| # | Item | Priority | Risk |
|---|---|---|---|
| S1 | Make semantic degradation loud (startup self-check + richer /health) | P0 | Low |
| S2 | Repath / backfill stale context_refs | P0 | Low |
| S3 | Bound the Referenced (authoritative) channel | P1 | Low |
| S4 | FTS integrity-check + rebuild-on-mismatch, loud trigger failures | P1 | Med |
| S5 | Harden the vec/FTS availability latch (verify-then-use) | P2 | Med |
| S6 | Wire or delete chunk embeddings (dormant subtopic rescue) | P2 | Low |

### S1 — Make degradation loud _(P0)_
**Problem.** Semantic search silently degrades to recency when `_VEC_AVAILABLE`/`_FTS_AVAILABLE`
latch False, or when `comms_embeddings` is empty. Nothing surfaces it (pre-`/health`).
**Evidence.** connection.py:205-221 (set-once latch + `logging.warning` only); the CT6 dark-months.
**Fix.** (a) Startup assertion in `app.main()`: after the eager `get_db()`, if vec is expected but
`embeddings_rows == 0` OR `vec_available` is False, emit a loud `RUNNER_WARNING`/log-error banner
(don't just `logger.info`). (b) Extend `retrieval_status()` with `fts_rows`, `fts_integrity_ok`,
and a `degraded: bool`. (c) Optional: a board `warning` post when a run starts in degraded mode so
the human sees it on the Command Center.

### S2 — Repath / backfill stale context_refs _(P0)_
**Problem.** context_refs written before storage-restructure point at `pathly/plans/<f>/…`; those
paths 404 on hydrate, so the authoritative channel serves nothing for those tasks.
**Evidence.** Verified: 4/5 live refs fail to hydrate (`⚠ artifact_not_found`, comms_formatters.py
:162-168). CT5 fixed the resolver for correct paths; existing DB rows still hold stale paths.
**Fix.** A one-shot migration/script that rewrites `context_refs` JSON on `comms_messages` from
`pathly/plans/<scope>/…` → `pathly/features/<scope>/…` when the features path exists on disk; skip
+ report the ones with no on-disk target. Idempotent, dry-run first. Mirror of
`scripts/backfill_comms_embeddings.py`.

### S3 — Bound the Referenced channel _(P1)_
**Problem.** The hydrated authoritative channel has no size cap; one large artifact can dominate
the prompt (13.6 K unbounded chars) — cost + context-window pressure.
**Evidence.** `_CONTEXT_CHAR_BUDGET=2000` is enforced only in the Context loop (comms_context.py
:295); Referenced is a raw `lines.extend(hydrate_lines)` (:248).
**Fix.** Add a `_REFERENCED_CHAR_BUDGET` (e.g. 6–8 K); when a hydrated section exceeds it, truncate
with a `… (section truncated — GET /comms/artifacts/<id>/section to read the rest)` affordance so
the agent can pull the remainder on demand. Prefer anchored refs (a section) over whole-file when
an anchor is available.

### S4 — FTS integrity + rebuild _(P1)_
**Problem.** External-content FTS synced only by triggers, no rebuild; a missing-trigger or
add-after-rows path silently omits messages from keyword search.
**Evidence.** Reproduced: rows inserted before triggers stay unsearchable via `MATCH`, no error.
`SELECT ... rowid NOT IN (SELECT rowid FROM comms_fts)` is NOT a sound check for external-content
FTS (returns 0 missing even when broken).
**Fix.** At startup (per DB path), run `INSERT INTO comms_fts(comms_fts) VALUES('integrity-check')`;
on failure run `INSERT INTO comms_fts(comms_fts) VALUES('rebuild')` and log loudly. Surface
`fts_integrity_ok` on `/health` (feeds S1).

### S5 — Harden the availability latch _(P2)_
**Problem.** One set-once process-global boolean gates the whole semantic subsystem; it latched
False when the first `get_db()` ran in a Flask worker thread (the CT6 deep cause).
**Evidence.** connection.py:73-102 (`_load_vec` retry) + 205-221 (one-time set). Fixed via eager
main-thread init in `app.main()`, but any non-`main()` entry (CLI, tests, embedded use) re-exposes
it.
**Fix.** Make store/search *verify-then-use*: `store_embedding`/`search_by_embedding` cheaply probe
`vec_version()` on their connection and lazily `_load_vec` if missing, rather than trusting the
global. Keep the global as a fast-path hint, not the sole gate.

### S6 — Wire or delete chunk embeddings _(P2)_
**Problem.** `comms_chunk_embeddings` has 0 rows in production; the subtopic-rescue merge in
`search_by_embedding` is built + verified-functional but never exercised — dead complexity.
**Evidence.** Verified via synthetic-chunk injection (works); live table empty.
**Decision needed.** Either populate child chunks on artifact post (`embed_artifact_async` already
computes them — confirm it's called and persisting), or remove the child scan to cut complexity.

---

## D. Sequencing

P0 first (S1 + S2 — both low-risk, high-trust-impact: they make the system honest about its own
state and repair the authoritative channel on real data). Then S3 + S4 (bound prompt size, close
the FTS omission). S5 + S6 are hardening/cleanup. Each item is independently shippable; S1's
`/health` extensions are the shared substrate the others report through.
