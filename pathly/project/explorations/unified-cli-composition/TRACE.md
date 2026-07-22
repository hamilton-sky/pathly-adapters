# Trace — unified-cli-composition P0 verification

## Files visited

| File | Lines | Finding |
|---|---|---|
| `src/pathly_orchestrator/http_server/blueprints/skills/editor_render.py` | 236–291 | `POST /skills/compose` endpoint: accepts `skill`, `adapter`, `transform` dict; calls `compose_skill` + `load_effective_manifest`; injects `{source_path}`, `{out_path}`, `{transform_kind}`/`{kind}` and `{summary_format}`; returns `{prompt, skill, composed: true/false}`; catches compose failure and returns 404 for truly unreadable skills |
| `src/pathly_orchestrator/skills/compose.py` | 63–92, 247–248, 256–265 | `load_effective_manifest` merges YAML + DB overrides, fails safe to YAML on DB error; missing-skill path at 247–248 returns raw body with no fragments; `no_defaults` flag at 256 skips default fragment list; fragment appending at 259–265 is cap-gated |
| `src/pathly_data/core/skills/composition.yaml` | 153–177 | Five transform-skill entries: `development/summarize`, `development/summarize-gist`, `development/summarize-detailed`, `development/analyze`, `development/split` — all with `no_defaults: true` and fragments `[client-file-output, artifact-transform]` |
| `src/pathly_data/core/skills/fragments/client-file-output.md` | 1–11 | Defines write-to-`{out_path}`, write-ONCE, no stdout, `ERROR:` prefix on failure |
| `src/pathly_data/core/skills/fragments/artifact-transform.md` | 1–15 | Defines read-source-once, write-output-once, never modify source, never re-read own output |
| `src/pathly_data/core/skills/development/summarize.md` | 1–18 | Topic-map task body with `<summary_format>` placeholder |
| `src/pathly_data/core/skills/development/analyze.md` | 1–24 | Markdown quality analysis task body |
| `src/pathly_data/core/skills/development/split.md` | 1–11 | Markdown restructuring task body with preservation rule |
| `.gitignore` | 30–33 | `*.summary`, `*.md.draft`, `*.md.analysis` all listed; comment labels them "Transient per-file AI capture artifacts" |
| `studio/src/renderer/src/services/skillCompose.ts` | 1–56 | `composeClientSkill(skill, adapter, transform, opts?): Promise<string|null>`; try/catch wraps apiFetch; returns `null` on network error, non-ok response, or missing/empty prompt; `ComposeTransform` interface with `source_path`, `out_path`, `kind` |
| `studio/src/renderer/src/components/CommandCenter/CommsPanel/ArtifactsView/summarizeArtifact.ts` | 14, 51–58, 107–148 | Calls `composeClientSkill` at 107–112; polls `.summary` file via `pollSummaryFile` (5×600ms) at 115; detects `^ERROR:/i` at 119–121, throws; bare-builder fallback at 125–131 used only when compose returned null |
| `studio/src/renderer/src/components/MarkdownEditor/EditorHeader/hooks/useEditorAgentActions.ts` | 6, 28–33, 38–52, 113–115, 136, 149–150, 186–189, 204, 215–216 | `resolveActionPrompt` (28–33) calls `composeClientSkill` for both actions; `isErrorResult` (38–40) matches `^ERROR:` case-insensitive; `pollForFile` (45–52) polls 5×600ms; both `handleSplit` and `handleAnalyze` check `isErrorResult` and branch to error state; `startedAt` stamped before spawn await |

## Code path

### Compose endpoint → client

1. **Renderer calls** `composeClientSkill('development/summarize', 'claude', {source_path, out_path, kind: 'summary'})` in `skillCompose.ts:37`.
2. `skillCompose.ts` POSTs `http://127.0.0.1:8765/skills/compose` with the payload; wraps in try/catch; returns `null` on any failure.
3. **`editor_render.py:236`** receives the POST. Validates `skill` is a string (`240`). Calls `compose_skill(skill_name, manifest, adapter_caps)` (`258`). On exception → 404.
4. `compose.py:247–248`: if skill not in `skills_map` → return raw body, `composed: false`. Otherwise proceed.
5. `compose.py:256`: if `spec.get("no_defaults")` → skip default fragment list (i.e. `progress-logging` not appended for transform skills).
6. `compose.py:259–265`: append fragments from spec — `client-file-output.md` + `artifact-transform.md` — cap-gated. Both are ungated (no `requires` clause) so always appended.
7. `_inject_prompt_vars` at `editor_render.py:273–280` substitutes `{source_path}`, `{out_path}`, `{transform_kind}` (or `{kind}`) into the assembled prompt body.
8. `_strip_leading_frontmatter` applied before return. Response: `{prompt: <assembled>, skill, composed: true}`.
9. **Renderer receives** the prompt string. Spawns CLI with prompt as argv.

### File-based capture (transform actions)

10. **CLI agent** writes result to `{out_path}` as final action (per `client-file-output` contract). On failure writes `ERROR: <reason>`.
11. **`summarizeArtifact.ts:115`** calls `pollSummaryFile(out_path)` — 5 tries × 600ms. Returns file content or null.
12. Line `119–121`: if content starts with `^ERROR:` → throws error (routed to pill-error + error toast at 142–148).
13. On success: content passed to `apiSetArtifactSummary` for writeback to `comms_artifacts` row.
14. `.summary` file deleted after read (per design).

### Editor Analyze/Split path

15. `useEditorAgentActions.ts:28–33` (`resolveActionPrompt`): calls `composeClientSkill` with `{source_path: forFile, out_path: analysisPath|draftPath, kind}`. Returns prompt or null.
16. On null: bare `buildAnalyzePrompt`/`buildSplitPrompt` used as fallback.
17. Optimistic `startedAt` stamped (line 120/191) BEFORE spawn await (line 158/224).
18. After spawn exits: `pollForFile` at 45–52 polls the derived path.
19. `isErrorResult` (38–40) checked at 136/204 → routes to error state (149–150/215–216) or success (chip reveal).

## Gaps

None. All code paths traceable from call site to file-capture result and error handling. No generated code, external service calls, or missing source encountered during the trace.
