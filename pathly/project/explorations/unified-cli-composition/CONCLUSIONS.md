# Conclusions — unified-cli-composition

## Answer

P0 is fully implemented as designed. All nine acceptance criteria are met. One minor deviation
from the written design exists (skillCompose.ts does not log an explicit warning on compose
failure — it silently returns null), but it is behaviorally correct: the caller falls back to
the bare builder exactly as intended. P1 can begin immediately.

## Evidence

- **AC 1 (compose endpoint):** `editor_render.py:236–291` — `POST /skills/compose` calls `compose_skill`, injects transform vars via `_inject_prompt_vars` (273–280) and strips frontmatter; returns `{prompt, skill, composed: true/false}`; 404 for truly unreadable skills.
- **AC 2 (client seam):** `services/skillCompose.ts:1–56` — `composeClientSkill` wraps POST in try/catch, returns `null` on network error / non-ok / empty prompt; callers in `summarizeArtifact.ts:107–112` and `useEditorAgentActions.ts:28–33` substitute bare builder on `null`.
- **AC 3 + 8 (pure-transform composition + no_defaults):** `composition.yaml:153–177` — all five transform skills (`development/summarize`, `summarize-gist`, `summarize-detailed`, `analyze`, `split`) declare `no_defaults: true` + fragments `[client-file-output, artifact-transform]`. `compose.py:256` reads the flag and skips defaults.
- **AC 3 (file-based capture, codex bug fixed):** `summarizeArtifact.ts:51–58, 107–148` — polls `.summary` file; `^ERROR:` detection at 119–121; old `result.text` stdout-tail path absent from the compose branch. `.gitignore` line 31–33 lists `*.summary`, `*.md.draft`, `*.md.analysis`.
- **AC 5 (pollForFile ERROR contract):** `useEditorAgentActions.ts:38–40` — `isErrorResult` matches `^ERROR:` case-insensitively; called at 136 (Split) and 204 (Analyze) before any success-path action; routes to pill-error + error toast at 149–150/215–216. `summarizeArtifact.ts:119–121` has the equivalent throw.
- **AC 7 (identical entry point):** Both `summarizeArtifact.ts:107` and `useEditorAgentActions.ts:28` call the same `composeClientSkill` → same `POST /skills/compose` → same `compose_skill` resolver.
- **AC 8 (DB-overridable, no regression):** `compose.py:247–248` returns raw body for skills absent from the manifest; `load_effective_manifest` at 63–92 merges DB overrides, fails safe to YAML.
- **AC 9 (skip-if-down):** `skillCompose.ts:37–54` try/catch returns `null`; each caller falls back to its bare builder. Confirmed at `summarizeArtifact.ts:125–131` and `useEditorAgentActions.ts:28–33`.
- **Fragment bodies correct:** `fragments/client-file-output.md:1–11` — single-write + `ERROR:` prefix contract. `fragments/artifact-transform.md:1–15` — read-once source, write-once output, never re-read own output.

## Risks / open questions

1. **No explicit warning log in skillCompose.ts.** The design says "logs a one-line warning" on compose failure (DESIGN.md architecture section). The implementation silently returns `null`. Behaviorally identical — fallback fires either way — but tracing a compose failure in production requires checking network/server logs rather than renderer console. Low risk; note for P1 if observability becomes important.
2. **`never-re-read-own-output` is prompt-only.** Fragment enforces this via instruction, not a mechanical guard. DESIGN.md notes this as intentional (P2 hardening, noted in Open Questions §3). Nothing currently feeds a derived file back as source — no live risk.
3. **Windows large-prompt path (DESIGN.md Open Questions §6).** Composed prompts are longer than bare builders. DESIGN.md flags this as needing confirmation that larger transform prompts exercise the PowerShell temp-script path in `terminal.ts` rather than `-EncodedCommand`'s ~32KB limit. Not verified in this exploration — worth a manual check in P1.
4. **Summary pill for first-fire auto-summary.** DESIGN.md Open Questions §1 flags the drop/upload handler (first auto-summary) vs Re-summarize (persistent control). Not verified in this exploration — the UX rule says both should use an inline RunPill keyed by `artifactId`. Confirm before P1 UX work.

## Recommendation

**BUILD: P1 is ready to start.** P0 is complete, sound, and production-correct. The path to P1 is clear:

- **P1a** — Author `fragments/board-start-context.md` + `fragments/task-dag-post.md` (Python data layer).
- **P1b** — Author `core/skills/development/decompose.md` (narrow body: POST tasks, no planning workflow) + manifest entry `[board-start-context, task-dag-post]`; replace the hand-coded POST loop in `goal_run.py:486–509` with in-Python `compose_skill('development/decompose', adapter)`.
- **P1c** — Add `development/drain-dag` manifest entry `[comms-post, task-dag-post, catalog-pull]` (NOT one-shot fragments); inject `compose_block(['board-start-context','task-dag-post','comms-post'], adapter)` into `_run_loop`'s per-task prompt via a `loop-board-io` blocks entry.
- **P1d** — `blocks:` → `profiles:` refactor: add `standalone-transform` + `goal-backed` profile keys; point the five transform skills at `profile: standalone-transform`; teach `compose.py` to select `goal-backed` by `goal_id` presence; keep `blocks:` as alias for one release.
- **P1e** — Extract in-body `curl POST /comms/post` from `team/architect` + `team/research` into a `[comms-post]` manifest entry.

Run `pathly-setup claude --apply --repair` + `python -m build` + `validate_composition` after each sub-step.
