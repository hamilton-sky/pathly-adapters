---
name: Conversation Prompts
---
# Skill Fragment Composition — Conversation Prompts

Scope gate: each conversation touches only the files listed. No FSM-transition logic in fragments.

---

## Conversation 1 — Fragment library + manifest (S1)

Create the fragment skills and the composition manifest. Do NOT change any resolver or
`build_prompt` yet — this conversation is pure data.

Files:
- `src/pathly_data/core/skills/fragments/progress-logging.md` — stub: a short heading + one
  line "(Track 2 will add: POST milestones to /runner/log as you work.)". Keep it minimal so
  it composes cleanly but adds no behaviour yet.
- `src/pathly_data/core/skills/fragments/feedback-protocol.md` — lift the "When blocked —
  feedback files" / feedback-routing prose currently duplicated in team/build, review, test.
- `src/pathly_data/core/skills/fragments/scout-choreography.md` — lift the Phase 1 analyze /
  Phase 2 scout / compress-findings prose.
- `src/pathly_data/core/skills/fragments/completion-report.md` — lift the `<usage>` parse +
  `log-agent-done` invocation contract.
- `src/pathly_data/core/skills/fragments/spawn-rules.md` — lift the sub-agent spawning rules
  (the part that assumes a Task/subagent capability).
- `src/pathly_data/core/skills/composition.yaml` — `version: 1`, `fragments_dir: fragments`,
  `defaults: [progress-logging, completion-report]`, and an **empty** `skills: {}` map.
  Leave the `team/build`/`team/review`/`team/test` entries commented out with a note that
  Conv 3 will add them *atomically* with body reduction. Rationale: a skill declared here but
  not yet reduced would emit its shared sections twice (once in body, once via fragment). Keep
  the manifest inert until Conv 3.

Verify: `python -c "import yaml,glob; m=yaml.safe_load(open('src/pathly_data/core/skills/composition.yaml')); [open(f'src/pathly_data/core/skills/{m[\"fragments_dir\"]}/{n}.md') for n in []]"` — i.e. confirm the YAML parses and every referenced fragment file exists.

Report: files created, and a diff note confirming fragment text was lifted (not paraphrased).

---

## Conversation 2 — Resolver + validator + wiring (S2)

Implement composition and wire it into both delivery paths.

Files:
- `src/pathly_orchestrator/compose.py` (NEW) — `compose_skill(skill, adapter_caps) -> str`.
  Reads `composition.yaml`, starts from `defaults + skills[skill]`, drops any fragment whose
  `requires:` capability is false in `adapter_caps`, concatenates `[stage body] + [fragments]`.
  Also `validate_composition()` raising on unknown fragment/skill, duplicate include, unknown
  capability.
- `src/pathly_orchestrator/fsm_ops.py` — `build_prompt()` calls `compose_skill` with the live
  stage adapter's caps instead of raw `_load_agent_text`.
- `pathly-setup` build path — materialise static `~/.claude/skills/pathly-*.md` via the same
  `compose_skill`.
- `tests/test_compose.py` (NEW) — validator rejects bad manifests; resolver gating
  (claude keeps spawn-rules, a can_spawn=false adapter drops it); **inert-seam check: with the
  empty `skills:` map, every existing skill composes byte-identical to its raw body** (proves the
  wiring changes nothing until Conv 3). The golden-snapshot test for the converted skills lands
  in Conv 3, not here.

Verify: `python -m pytest tests/ -q`.

Report: resolver + validator behaviour, inert-seam result (no skill changed), both call sites wired.

---

## Conversation 3 — Convert build/review/test + anti-drift (S3)

Now reduce the three skills to stage bodies and prove the adapters stay in sync.

Files:
- `src/pathly_data/core/skills/composition.yaml` — **uncomment / add** the `team/build`,
  `team/review`, `team/test` entries (with `{ name: spawn-rules, requires: can_spawn }` where
  spawning is needed). Do this **in the same commit** as the body reduction below.
- `src/pathly_data/core/skills/team/build.md`, `.../review.md`, `.../test.md` — remove the
  sections now provided by fragments; keep only stage-specific steps + a reference that
  fragments are composed in. Each shared section must end up in **exactly one** place (the
  fragment), never both.
- `tests/test_compose.py` (extend) — **golden snapshot** for claude: composed `team/build`,
  `team/review`, `team/test` match a reviewed snapshot; assert each shared section (logging,
  feedback, scout, completion, spawn) appears exactly once.
- Run `pathly-setup claude --apply` then `python -m build` to regenerate all three adapters.
- `tests/test_adapter_staleness.py` (NEW or extend) — committed adapter skill must equal the
  composed core output; fail on drift.

Verify: `python -m pytest tests/ -q` + confirm `git status` shows regenerated adapter files,
no hand edits to `_meta`.

Report: skills converted, manifest entries added atomically, snapshot + staleness tests added,
adapters regenerated, full suite green.
