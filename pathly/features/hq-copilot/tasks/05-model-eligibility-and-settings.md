# Add HQ model eligibility and settings

Type: task
Status: resolved
Blocked by: 01
Test first: yes

A model that cannot hold the packet will silently drop board facts, so
HQ must refuse unsuitable models instead of degrading quietly.

1. App settings (user-set, same store as the other `app_settings`):
   `hq.default_model` (default `"qwen3-8b"` — user has 24 GB unified
   memory; `"phi-4-mini"` stays the zero-friction fallback),
   `hq.context_budget_tokens` (default from ticket 01), and
   `hq.packet_order` (`"attention"` default, `"progress"` alternative
   — ticket 01). Document all three in the settings help text as
   HQ-only.
2. Eligibility: `hq_context.py` (or a tiny `hq_models.py` next to it)
   gains `hq_eligible(model_id) -> bool` — true when the model's known
   context window is at least `2 * budget + 4000` tokens (packet +
   prompt + answer headroom). The context-window table starts from what
   Studio's model catalog already knows; unknown models are ineligible
   until added (fail closed: an unknown window is not assumed large).
3. Record in the Answer which runtime serves Studio's downloaded models
   and where its context limits are declared (map.md Open questions:
   this ticket closes it). Verified 2026-10-14: the runtime is
   **node-llama-cpp v3 in the Electron main process**
   (`studio/src/main/ipc/llm.ts`), NOT a separate HTTP server — it
   exposes `llm:chat` over IPC with a hardcoded `maxTokens: 512`, and
   `llm:download` fetches GGUFs from HuggingFace into
   `<userData>/models` (Ollama at `localhost:11434` is the supported
   fallback via `llm:ollamaChat`/`llm:ollamaPull`). Two consequences
   this ticket must handle: (a) register `qwen3-8b` in `MODEL_REGISTRY`
   (it is the chosen default but not registered — only qwen3-4b,
   qwen2.5-coder-7b, phi-4-mini, deepseek-r1-1.5b are; follow the
existing `hf:` URI pattern); (b) confirm 512 max tokens is enough for
   HQ status answers, or make it configurable per caller.
4. `GET /hq/context` (ticket 03) includes `eligible_model: bool` for the
   currently selected HQ model, so the panel can warn before the user
   sends a message the model cannot hold.

## Not in this ticket

- Downloading or adding new models: the Studio picker owns that.
- Changing the picker UI itself: ticket 06 shows the manifest; picker
  changes are out of scope.

## Done when

- `python -m pytest tests/hq_copilot/test_models.py -q -p no:cacheprovider` passes and covers: default settings resolve to `phi-4-mini` and ticket 01's budget; a 128k-window model is eligible at default budget; a 4k-window model is ineligible; an unknown model id is ineligible; `GET /hq/context` reports `eligible_model` consistently with `hq_eligible`.
- `python scripts/check_file_size.py` exits 0.

```check
$ python -m pytest tests/hq_copilot/test_models.py -q -p no:cacheprovider
exit 0
prints passed
```

## Reference

- spec.md § Interfaces (settings), § Edge cases (model context < budget)
- `src/pathly_orchestrator/db/queries/app_settings.py` (settings pattern)
- `studio/src/renderer/src/components/` HQ panel (model catalog shape; read-only)

## Answer

Implemented 2026-10-14.

1. **Settings.** New HQ-only section in
   `src/pathly_orchestrator/db/queries/hq_settings.py`
   (`hq.default_model` → `qwen3-8b`, `hq.context_budget_tokens` →
   `6000`, `hq.packet_order` → `attention`|`progress`; garbage values
   fall back to defaults, never break assembly). Split out of
   `app_settings.py` (it sits on the 400-line ratchet) and re-exported
   from it — the same split+re-export pattern as `comms_hydrate`.
   `hq_context._packet_order` now uses the shared accessor.
   **Correction:** the Done-when line naming `phi-4-mini` as the
   default is stale — ticket 01 settled `hq.default_model = "qwen3-8b"`
   (24 GB machine; phi-4-mini stays the fallback), and the tests
   assert the settled default.
2. **Eligibility.** New `src/pathly_orchestrator/hq_models.py`:
   `MODEL_CONTEXT_WINDOWS` (qwen3-4b/8b + qwen2.5-coder-7b → 32768,
   phi-4-mini + deepseek-r1-1.5b → 128000) and `hq_eligible(model_id,
   budget=None)` — true when window >= 2*budget + 4000; unknown ids
   fail closed (ineligible).
3. **Runtime + Studio.** Recorded per the ticket: downloaded models are
   served by **node-llama-cpp v3 in the Electron main process**
   (`studio/src/main/ipc/llm.ts`); Studio's MODEL_REGISTRY declares
   **no context limits at all** — this closes the map.md open
   question: the eligibility table in `hq_models.py` is the first
   place context windows are pinned for HQ (native architecture
   values, conservative). (a) `qwen3-8b` registered in
   `MODEL_REGISTRY` following the `hf:unsloth/...` pattern. (b)
   `maxTokens` is now **per-caller configurable** on `llm:chat`
   (`maxTokens?: number`, default 512 — existing callers unchanged;
   preload + `global.d.ts` mirror updated). 512 stays the default:
   enough for typical HQ status answers (~350 words), and the HQ
   panel (ticket 06) can raise it per call.
4. **Endpoint.** `GET /hq/context` now returns `model` and
   `eligible_model` (from `?model=`, else the `hq.default_model`
   setting), so the panel can warn before a message the model cannot
   hold.

Tests: `tests/hq_copilot/test_models.py` (6 tests: settled defaults,
overrides + garbage fallback, window eligibility, fail-closed unknown,
endpoint consistency). Full hq_copilot dir: 30 passed.
`check_file_size.py` exits 0. Full regression
(`tests/comms_board tests/db tests/http_api tests/hq_copilot`): 918
passed, 2 skipped, 2026-10-14 (clean clone at the Mac's commit era,
venv on the assistant's machine).
