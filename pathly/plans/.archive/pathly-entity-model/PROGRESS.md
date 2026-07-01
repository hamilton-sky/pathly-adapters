# Progress — pathly-entity-model

_Last updated: 2026-06-29_

| # | Conversation | Phase | Stories | Status | Notes |
|---|---|---|---|---|---|
| 0 | Guard: `_safe_topic` + slug column | Phase 0 | S0.1, S0.2 | TODO | `_safe_topic` RAISES immediately (not WARN). Add guard to `fsm_ops.py:68` and `argv.py:13`. Idempotent migration for `comms_messages.slug` + UNIQUE index. Tests: `tests/test_fsm_ops.py`. |
| 1 | Bug fix: slug routing at all collapse sites + RESERVED set extension | Phase 1 | S1.1, S1.2, S1.3, S1.4, S1.5 | TODO | Split `terminal.py` FIRST. Create `supervisor/slug.py`. Thread `topic=slug` at all 10 verified sites. Add `goals/` probe to `_resolve_storage_path`. Extend Studio RESERVED set. One real end-to-end consultation decompose. |
| 2 | Artifact contract (ATOMIC — one commit) | Phase 2 | S2.1, S2.2, S2.3, S2.4, S2.5 | TODO | Exactly 7 artifacts in one commit. `artifact-manifest.yaml`, `artifact-register.md`, `dag-sketch.md`, `composition.yaml` entry, `_decompose_planner` edit, `ensure_attached`, 4-adapter sync. Build gate must fail if dag-sketch referenced but absent. |
| 3 | Sidebar: `CardSidebar` + `loadCards` store split | Phase 3 | S3.1, S3.2, S3.3, S3.4 | TODO | Renderer-only. `CardSidebar` behind flag with `FeatureSidebar` fallback. `cards` slice + derived `features` getter. Goal Decompose/Run buttons. Lesson click opens MarkdownEditor. TypeScript compile clean. |
