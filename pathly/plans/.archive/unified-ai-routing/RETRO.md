# Retro — unified-ai-routing

**Outcome:** shipped on `feat/unified-ai-routing` (commits `5bba33ee` + `4f5e4092`).
Full team flow: STORM → PLAN → DESIGN → BUILD (6 conversations) → REVIEW → TEST → RETRO.
Final gates: **pytest 868 passed / 5 skipped · tsc web+node 0 · vitest 26 · orphan grep clean.**

## What shipped
AI dispatch unified into three single-responsibility pieces — **CLI Engine** (unchanged),
app-level **AI Model Manager** (Ollama/GGUF/Brightsky), and a small **Router** (model ⊕ engine).
Board artifacts summarize through the Router (per-artifact target + Re-summarize); the server
emits a `summary_request` SSE instead of ever running inference. The broken server-side
summarizer (`inference.py` + `inference:*` settings + `SummarySettings.tsx` + `/summarize`
route) is fully removed. Phase boundaries post to the board in both modes, excluded from
injected context so headless prompts stay lean.

## What went well
- **Clean component boundaries** made the build decomposable into 6 conversations, each
  verified (typecheck/tests) before the next — interdependencies (Manager→Router→consumers)
  sequenced naturally.
- **Additive-first ordering**: new path proven (Conv 1–4) before any deletion (Conv 5).
- **Board-integrated throughout** — every phase + decision + artifact is on the Command Center.
- **Adversarial review earned its cost**: it caught a *silent* correctness regression the full
  green gate suite missed.

## What went wrong — and the lessons
1. **A builder timed out mid-deletion (Conv 5)** and left a broken tree (dangling refs to
   deleted symbols). Recovered by finishing the test cleanup + verification in the orchestrator.
   → *Lesson: scope destructive conversations smaller — "delete + migrate 3 callers + remove 4
   tests + update docs" was too much for one agent turn.*
2. **I dismissed real Pyright diagnostics as "stale."** `messages.py "No parameter named
   summarize"` was the actual blocking bug, not a mid-edit artifact. → *Lesson: never wave off
   `reportCallIssue`/`reportMissingImports` without proof; "stale" is only safe for
   import-resolution that a passing runtime test disproves.*
3. **A cwd drift silently scoped a Grep to the wrong directory**, so my "docs are clean" check
   missed three stale summarizer references. → *Lesson: the Grep tool inherits cwd; pass explicit
   paths for repo-wide checks, and re-run from a known root.*
4. **Stub-heavy tests hid caller/callee signature drift** — `index_artifact_async` was
   monkeypatched to `lambda *a, **k`, absorbing the bad kwarg. → *Lesson: added a
   signature-binding regression test; prefer at least one unstubbed end-to-end path per critical
   handler.*

## Deferred follow-ups (documented, out of acceptance scope)
- Brightsky one-shot transport: run the token-refresh the shared client does (near-expiry fails).
- Brightsky protocol framing duplicated across `brightsky.ts` and `brightskyClient.ts` — extract shared constants.
- aiRouter **engine** path stores raw stdout; parse the result for engine-typed summarize selections.
- `runModel` transport branching has no dedicated unit test (dispatch + wiring are covered).
- Pre-existing SOLID over-cap files (`messages.py` 646, `comms_context.py` 502) — split.
- `embed_summary` §3a (feed summary into the search vector) removed with the server path — decide whether to restore client-side.
