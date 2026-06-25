# Review — unified-ai-routing (branch `feat/unified-ai-routing`, commit 5bba33ee)

**VERDICT: RESOLVED** — the one BLOCKING regression (stale `summarize=False` kwarg →
section indexing skipped on `/comms/post`) is fixed; everything else was already clean.

## Resolution (orchestrator)
- **BLOCKING-1 fixed:** removed `summarize=False` at messages.py:280 — the call now matches
  the `index_artifact_async(artifact_id, path, scope, broadcast_fn)` signature. Added a
  deterministic regression test `tests/test_post_artifact_indexing.py` that binds the
  post-path call against the real signature (the gates' `lambda *a, **k` stubs hid the bug).
- **Cheap non-blocking also fixed:** `handleSummaryRequest` now releases its dedup guard on
  failure (was a permanent per-session no-retry); stale doc comments updated (root CLAUDE.md,
  src CLAUDE.md package list, migrations.py); coupled `summarize=False` comment corrected.
- **Deferred as documented follow-ups:** Brightsky token-refresh on the one-shot path,
  Brightsky protocol de-dup, aiRouter engine-result parsing, and the pre-existing over-cap
  `messages.py`/`comms_context.py` splits (this change net-shrank `hydrate.py` by 188 lines).
- **Re-verified:** pytest **868 passed**; tsc web+node **0**; vitest **26** (+1 regression test).

## Gate results (re-run by reviewer, not copied from VERIFY.md)

| Gate | Command | Result |
|---|---|---|
| Python tests | `PYTHONPATH=src python -m pytest tests/ -q` | **PASS** — 867 passed, 5 skipped (269s) |
| Renderer typecheck | `studio/node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json` | **PASS** — exit 0 |
| Main typecheck | `studio/node_modules/.bin/tsc --noEmit -p studio/tsconfig.node.json` | **PASS** — exit 0 |
| Renderer unit tests | `studio && node_modules/.bin/vitest run` | **PASS** — 6 files, 26 tests |

All four gates green — matches VERIFY.md. NOTE: gates do **not** catch the blocking
finding below (the two relevant tests monkeypatch `index_artifact_async` to a no-op that
swallows the bad kwarg via `**k`).

## Findings

| Severity | File:line | Issue | Fix |
|---|---|---|---|
| **BLOCKING** | `src/pathly_orchestrator/http_server/blueprints/comms/messages.py:280` | `index_artifact_async(...)` is called with `summarize=False`, but Conv 5 changed its signature to `(artifact_id, path, scope='', broadcast_fn=None)` — no `summarize` param. This raises `TypeError`, caught by the `except Exception` at L282-283 and logged at debug only. Net effect: **section indexing (the `/comms/artifacts/<id>/section` hydration index) is silently skipped for every `.md` artifact posted via `/comms/post`** — including agent-posted artifacts in headless runs. The sibling `/comms/attach` path was migrated correctly (artifacts.py:94 drops the kwarg); only the post path was missed. Confirmed at runtime: `inspect.signature` shows no `summarize`; the call raises `TypeError: index_artifact_async() got an unexpected keyword argument 'summarize'`. Uncaught by gates because `test_comms_summary_request_sse.py:44` and `test_comms_sections.py:35` stub the function with `lambda *a, **k: None`. | Delete the `summarize=False,` argument at messages.py:280 (and the now-stale "pass summarize=False" comment at L270). Match the corrected attach-path call. Optionally add a regression test that posts an `.md` artifact via `/comms/post` (without stubbing `index_artifact_async`) and asserts `get_artifact_sections` is non-empty. |
| NON-BLOCKING | `studio/src/renderer/src/services/modelManager/transports/brightsky.ts:22-31` | One-shot reads `accessToken` straight from the store and never refreshes it. The shared `brightskyClient.sendMessage` always calls `maybeRefreshToken()` first (brightskyClient.ts:192). A near-expiry/expired persisted token → WS rejects → summary silently fails (best-effort, degrades to no summary). | Before opening the socket, run the same refresh-if-stale logic (extract `maybeRefreshToken` to a shared helper, or expose a `refreshIfStale()` on the store and await it here). |
| NON-BLOCKING | `brightsky.ts` (whole file) | Re-implements the Brightsky WS protocol (`create_session_with_message`, `stream_chunk`/`stream_end`, `sharedFields`, token query-param) independently of `brightskyClient.ts`. If the server protocol changes, chat and one-shot drift. The header documents this as a deliberate tradeoff (shared client is coupled to the chat store). | Acceptable for now; consider extracting the protocol-framing constants into a shared module so both paths import one source of truth. |
| NON-BLOCKING | `studio/src/renderer/src/services/aiRouter.ts:59` | Engine path resolves with the raw stdout `tail` on exit. For `claude --output-format json` the tail is JSON, not prose — so an `engine`-typed summarize selection stores raw JSON as the artifact summary. Works for the `model` path (the primary one); engine-summarize is a secondary path. | Document the limitation, or parse the engine result (reuse `parse_result`/`_extract_json_payload` shape) before resolving. Not load-bearing for the model-based default. |
| NON-BLOCKING | `handleSummaryRequest.ts:53-54` | `handled.add(artifactId)` runs before the await and is never removed, so a transient summarize failure (model not loaded, network blip) permanently marks the artifact handled for the session — the SSE path won't retry. Mitigated by the manual Re-summarize button. | Add to `handled` only on success, or remove on failure in the catch. |
| NON-BLOCKING | `src/pathly_orchestrator/http_server/blueprints/comms/messages.py` (646 lines), `runner/comms_context.py` (502), `runner/hydrate.py` (441), `CommsPanel.tsx` (259) | Over the SOLID caps (400 Python / ~150 React). All **pre-existing**; this change net-grew `messages.py` by ~30 lines and net-*shrank* `hydrate.py` by 188. Every genuinely new file is within caps. | Out of scope for this change; flag for a follow-up split of `messages.py`. |
| NON-BLOCKING | `src/pathly_orchestrator/CLAUDE.md:158`, `src/pathly_orchestrator/db/migrations.py:292` | Stale comments still reference the deleted `inference.py` / "inference service, Phase 4" summarizer. | Update both comments to reflect client-side summarization. |
| NON-BLOCKING | `CommsMsgList.tsx:35-46` | The search overlay renders results as `MsgCard`, not `PhaseRow`; a `phase` message surfaced in search would show as a full card. `phase` is not in `_EMBED_TYPES`, so it won't appear in semantic search — cosmetic only. | Branch on `m.type === 'phase'` in the search map too, for consistency. |
| NON-BLOCKING | `PhaseRow.tsx:21` | Renders `{m.time} ago`; when `relativeTime` returns `"now"` the row reads "now ago". | Special-case `"now"`, or have PhaseRow drop the " ago" suffix. |

## Areas verified clean

- **Layer rule:** `runner/comms_context.py` and `runner/hydrate.py` import only `db.*`/`runner.*` — no `http_server` import (grep-confirmed). `_phase_board.py` (http_server layer) importing `sse` is allowed.
- **Brightsky leak-safety:** `cleanup()` clears both timers and closes the socket on every settle path; `succeed`/`fail` are `settled`-guarded; `onclose`/`onerror`/timeouts all route through them. No leak on success/error/timeout.
- **aiRouter engine lifecycle:** subscribes to `onExit` before spawn, filters own `tabId`, `settled` flag ⇒ unsubscribe exactly once, rejects on non-zero exit, spawn `.catch` tears down. `onExit` signature `(tabId, exitCode?, tail?)` matches global.d.ts:167.
- **Conv 5 deletions:** `inference.py` + 4 test files + `SummarySettings.tsx` deleted; orphan grep for the removed symbols is clean (only comment-only mentions remain). `index_artifact_async` cleanly dropped `summarize`/`backend`/`embed_summary` (one stale caller — the BLOCKING item above).
- **Contract relaxation (messages.py:140-146):** `summary_backend` coerced to `None` for non-strings; only `'minilm'` is load-bearing (suppression). `embed_summary` accepted as a no-op. No injection gap — value is only compared to the literal `'minilm'`, never executed/interpolated.
- **Server-trigger (`_summary_request.py`):** precedence is per-artifact → app default → None; runs no inference; never raises (wrapped); off-sentinel (`id=='__off__'`) and `minilm` both short-circuit before broadcast. `.md`/`.txt`-only gate matches the client rule.
- **Selection round-trip:** Off (`{type:'model',id:'__off__'}`) passes `set_default_summary_selection` validation (non-empty id), persists, and is correctly re-decoded to `OFF_VALUE` by `AiTargetSelector` and skipped server-side — consistent end to end.
- **Migration:** `summary_selection TEXT` added via the idempotent additive-migration loop (nullable → app-default fallback). Existing rows untouched.
- **Phase board (Conv 6):** `record_phase` → `post_phase_to_board` calls `post_message` with valid args; `phase` excluded from `retrieve_board_context._is_context`; `PhaseRow` handles missing `from`/`author`; `Message.type` union includes `'phase'`.
