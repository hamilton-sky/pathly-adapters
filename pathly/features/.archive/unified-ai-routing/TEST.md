# Test — unified-ai-routing (branch `feat/unified-ai-routing`, commit `4f5e4092`)

**VERDICT: PASS** — all 18 acceptance criteria across US-1…US-6 are met. Two are
PASS-WITH-NOTE (non-blocking gaps, explained inline); none fail. The one BLOCKING
regression the reviewer flagged (section indexing silently skipped on `/comms/post`)
is fixed and verified functionally end-to-end (sections actually populate, not just
kwarg-binding).

## Gate results (re-run by tester)

| Gate | Command | Result |
|---|---|---|
| Python tests | `PYTHONPATH=src python -m pytest tests/ -q` | **PASS** — 868 passed, 5 skipped (167s) |
| Renderer typecheck | `studio/node_modules/.bin/tsc --noEmit -p tsconfig.web.json` | **PASS** — exit 0 |
| Main typecheck | `studio/node_modules/.bin/tsc --noEmit -p tsconfig.node.json` | **PASS** — exit 0 |
| Renderer unit tests | `studio && node_modules/.bin/vitest run` | **PASS** — 6 files, 26 tests |
| Orphan grep | `grep -rn "summarize_content\|summarize_async\|get_summary_backend\|SummarySettings\|apiGetSummaryBackend"` | **CLEAN** — 0 matches |
| Targeted suite | `pytest test_post_artifact_indexing test_comms_artifact_summary_writeback test_comms_summary_request_sse test_phase_board_post` | **PASS** — 18 passed |

Note (matches REVIEW.md): the broad gates do not catch the section-indexing bug because
sibling tests stub `index_artifact_async` with `lambda *a, **k`. The fix is independently
verified by `test_post_artifact_indexing.py` (binds against the real signature) **and** by a
live functional run below.

## Live functional verification (section indexing — the fixed blocker)

Posted a `.md` artifact via `/comms/post` against a real DB (no stubs), waited for the async
indexer, then queried the section index + hydration route:
- `comms_artifact_sections` populated: `[('doc','Doc'), ('storage','Storage'), ('api','API')]`
- `GET /comms/artifacts/<id>/section?anchor=storage` → 200, returns the correct `## Storage`
  section text.

This proves the `summarize=False` removal at `messages.py:280` restored end-to-end section
indexing — not merely kwarg correctness.

## Per-acceptance results

### US-1 — AI Model Manager (lift out of HQ)
| Acceptance | Result | Evidence |
|---|---|---|
| `modelManager` exposes catalog + `runModel(id, prompt) → {text, cost_usd?}` dispatching Ollama (HTTP) / GGUF (IPC) / Brightsky (WS) | **PASS** | `modelManager/index.ts` re-exports `MODEL_CATALOG`+`runModel`+`RunResult`. `runModel.ts:35-66` dispatches: `brightsky`→`runBrightsky` (WS, `transports/brightsky.ts`), Ollama tag present→`runOllama` (HTTP POST `:11434/api/generate`, `transports/ollama.ts`), GGUF cached→`runGguf` (`window.pathly.llm` via `llmBridge`, `transports/gguf.ts`). `RunResult` = `{text, cost_usd?}` (`transports/types.ts`). |
| HQ `ModelSelector` consumes `modelManager`; HQ chat behavior unchanged | **PASS** | `ModelSelector.tsx:3` imports `MODEL_CATALOG` from `services/modelManager`. The ONLY HQ file changed on this branch is `ModelSelector.tsx` (`git diff fcbae34b..HEAD`: 4 lines). `useHQ.tsx handleSend` (its `askLlm`/`askOllama`/`brightskyClient.sendMessage` streaming path) is untouched. |
| No duplicate catalog remains in HQ | **PASS** | One physical array: `data/models.ts WEB_LLM_MODELS`; `catalog.ts:15 MODEL_CATALOG = WEB_LLM_MODELS` re-exports it. No second catalog definition exists. `useHQ.tsx`/`ModelCard.tsx` still import `WEB_LLM_MODELS` directly, but that's the same single array (a storage detail), not a duplicate catalog. |

### US-2 — Router (model ⊕ engine)
| Acceptance | Result | Evidence |
|---|---|---|
| `aiRouter.runJob(job, selection)` routes `model`→modelManager, `engine`→CLI Engine spawn | **PASS** | `aiRouter.ts:74-82`: `selection.type==='model'`→`runModel(selection.id, job.prompt)`; else `runEngine`→`buildHeadlessArgv`+`window.pathly.terminal.spawn`. Off sentinel throws (L75-77). Tested: `aiRouter.test.ts` (model dispatch, engine argv+spawn+lifecycle, cwd, non-zero-exit reject, Off reject). |
| A unified selector lists models ⊕ CLI engines in one control | **PASS** | `AiTargetSelector.tsx`: one `<select>` with `<optgroup label="Models">` (catalog + Brightsky) and `<optgroup label="CLI Engines">` (`ADAPTER_META`, headless-incapable shown disabled). Lives in `shared/` for HQ + ArtifactsView reuse. |
| No Anthropic API-key path anywhere | **PASS** | Grep for `api[_-]key`/`x-api-key`/`ANTHROPIC_API_KEY`/`sk-ant` across `src/` + `studio/src/`: only hits are `pathly_hooks/classify_feedback.py` (pre-existing optional telemetry classifier, NOT touched on this branch, NOT in the router/summary path). The model/engine path uses local transports + CLI argv only. |

### US-3 — Board artifact summary via Router + per-artifact selection
| Acceptance | Result | Evidence |
|---|---|---|
| Drop/pick runs `aiRouter.runJob({kind:'summarize'}, selection)`; result saved to `comms_artifacts.summary` | **PASS** | `ArtifactsView.tsx:77-81` wires `AiTargetSelector`→`onSummarySelectionChange`; `summarizeArtifact.ts` reads file→`runJob({kind:'summarize'})`→POST `/comms/artifacts/<id>/summary`. Server `artifacts_summary.py:49-106` persists `summary`. Tested `summarizeArtifact.test.ts` (post→read→runJob→writeback, Off skip, non-md skip, empty-text no-writeback). |
| `comms_artifacts` gains persisted `summary_selection {type,id}`; re-summarize action exists | **PASS** | Migration `migrations.py:433` adds `summary_selection TEXT` (idempotent). Query family `db/queries/comms_summary.py`. Route `/comms/artifacts/<id>/selection` (`artifacts_summary.py:112-160`). Re-summarize: `ResummarizeButton.tsx` → `resummarizeArtifactByMessage`. Tested `test_comms_artifact_summary_writeback.py` (column exists; selection persists for model + engine; 400/404 paths). |
| Old `localStorage` upload-summary dropdown replaced by the unified selector | **PASS** | Grep for `pathly.comms.uploadSummary`/`uploadSummary`: 0 matches. `ArtifactsView.tsx:28-30` comment: "Conv 3 replaced the old localStorage backend dropdown" with `AiTargetSelector`. |

### US-4 — Server-triggered summary without server-side inference
| Acceptance | Result | Evidence |
|---|---|---|
| Server enqueues a summary request (SSE); client runs Router and posts result back | **PASS** | Post path `messages.py:289-300` and attach path `artifacts.py:103-122` both call `emit_summary_request` (`_summary_request.py`) → broadcasts `summary_request` over comms SSE with server-resolved `selection`. Client `handleSummaryRequest.ts` runs `summarizeArtifactById`→aiRouter→writeback. Tested both sides: `test_comms_summary_request_sse.py` (emits exactly 1 request with resolved selection) + `handleSummaryRequest.test.ts` (dispatch, Off skip, missing-field guard, dedup, never-throws). |
| No client connected ⇒ filename-only (best-effort); no server inference | **PASS** | `_summary_request.py` runs zero inference (structural — the in-process summarizer was deleted in Conv 5; grep for inference calls in `comms/` blueprints is clean). No selection resolved ⇒ emits nothing (filename-only). `minilm`/`__off__` short-circuit before broadcast. Tested: `test_no_selection_emits_no_summary_request`, `test_minilm_backend_emits_no_summary_request`. |

### US-5 — Remove the old summarizer (cleanup)
| Acceptance | Result | Evidence |
|---|---|---|
| `runner/inference.py` + callers removed | **PASS** | `inference.py` absent. No inference call survives in `comms/` blueprints (grep clean). |
| `inference:summary_backend`/`inference:ollama_model` + helpers removed | **PASS** | No `inference:*` keys or `get/set_summary_backend` helpers in `db/queries/app_settings.py`. |
| `Settings/SummarySettings.tsx` + API helpers removed | **PASS** | File absent. Orphan grep for `SummarySettings`/`apiGetSummaryBackend`: 0 matches. |
| `test_inference.py`, `test_summary_backend.py`, `test_comms_artifact_summarize.py` removed/rewritten | **PASS** | All three absent; replaced by `test_comms_artifact_summary_writeback.py` + `test_comms_summary_request_sse.py`. |
| New tests cover `aiRouter`, `modelManager` dispatch, server-trigger handoff | **PASS-WITH-NOTE** | aiRouter dispatch: `aiRouter.test.ts`. Server-trigger handoff: `handleSummaryRequest.test.ts` + `test_comms_summary_request_sse.py`. **modelManager dispatch (`runModel.ts` Ollama/GGUF/Brightsky branching) has no dedicated unit test** — `aiRouter.test.ts` mocks `runModel` out. The aiRouter→runModel wiring is asserted and the transport branch is typechecked, but runModel's internal transport selection is not directly exercised. Minor coverage gap, not a regression; graded PASS-WITH-NOTE. |
| `pytest -q` + both `tsc` pass; no references to deleted symbols | **PASS** | 868 passed / 5 skipped; tsc web+node exit 0; orphan grep clean. |
| (Blocker re-check) section indexing on `/comms/post` works | **PASS** | `messages.py:275-280` calls `index_artifact_async(art_id, path, scope=, broadcast_fn=)` — no `summarize` kwarg (signature `(artifact_id, path, scope='', broadcast_fn=None)`). `test_post_artifact_indexing.py` passes; live run populates `comms_artifact_sections` + hydration returns the right section. |

### US-6 — Phase-boundary board posts (both modes)
| Acceptance | Result | Evidence |
|---|---|---|
| `record-phase` handler posts a `phase`-type board message on PHASE_START/PHASE_DONE (best-effort, never blocks) | **PASS** | `telemetry.py:394-401` (`/record_phase`) calls `post_phase_to_board` for every event_type, wrapped in try/except. `_phase_board.py:20-56` `post_phase_to_board` → `post_message(type="phase", ...)` + SSE broadcast; never raises. Tested `test_phase_board_post.py` (3 passed). |
| `phase` UI-visible but EXCLUDED from `retrieve_board_context` | **PASS** | `comms_context.py:205-208` `_is_context` returns False for `type=="phase"`. `phase` is not in `_EMBED_TYPES`, so it also never surfaces via semantic search — prompt-injected board block does not grow. |
| Interactive (team-http) and headless (supervisor) populate the board identically; no CLI-engine execution change | **PASS** | Both modes log phases through the same `/record_phase` endpoint, which is the single post site — no skill-only divergence. `post_phase_to_board` only writes a board row + SSE; it does not alter argv or CLI execution. UI: `CommsMsgList.tsx:90-91` renders `<PhaseRow>` for `m.type==='phase'`; `Message.type` union includes `'phase'` (typecheck passes). |

## Non-blocking notes (carried from REVIEW.md; cosmetic / out-of-scope — not test failures)
- `PhaseRow.tsx:21` renders `{m.time} ago`; when `relativeTime` is `"now"` it reads "now ago" (cosmetic).
- `CommsMsgList` search overlay renders results as `MsgCard` not `PhaseRow` — but `phase` is not embedded, so it can't appear in semantic search (cosmetic-only).
- `aiRouter.ts:59` engine path resolves raw stdout tail; for `claude --output-format json` an engine-summarize stores raw JSON. Secondary path; model path (the default) is unaffected.
- `brightsky.ts` one-shot reads `accessToken` without `maybeRefreshToken()`; near-expiry token → WS reject → summary silently degrades (best-effort). Deferred follow-up.
- `messages.py` (646), `comms_context.py` (502), `hydrate.py` (441) over the 400-line SOLID cap — all pre-existing; this change net-shrank `hydrate.py` by 188 lines. Flagged for a follow-up split.
- modelManager `runModel` transport dispatch lacks a dedicated unit test (see US-5 PASS-WITH-NOTE).
