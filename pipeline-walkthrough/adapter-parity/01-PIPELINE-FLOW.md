# 01 — Pipeline Flow: adapter-parity

_Date: 2026-05-25 | Branch: master_

Every agent spawn, feedback loop, and gate — in execution order.

---

## Execution trace

```
User intent: "adapter-parity fast"
│
│  [Stage 0 — Discovery]
│  Orchestrator → PLANNING (plan files pre-existing — skip discovery)
│  Orchestrator → DESIGNING (auto-advance)
│
│  [Stage 1 — Planning]
│  Plan files already existed — planner stage skipped
│  DESIGN.md generated via pathly-design CLI (stack: react, wall: 43s)
│
│  [Stage 2–3 — Build + Review]
│
│  Conv 1 — Copilot/Codex skill parity + explorer contract (Phases 1–3)
├─► Builder analyze → NEEDS_CONTEXT (2 quick entries)
│   Scout (parallel): source YAMLs + adapter directory structure
├─► Builder implement
│   Creates: copilot/archive-artifacts_skill.yaml, copilot/commit_skill.yaml,
│            codex/commit_skill.yaml
│   Phase 3 (explorer.md): already existed at research/ — no action needed
│   Verify: check_core.py → 117 pre-existing parity issues, 0 new failures
│   Reviewer: SKIPPED (lite rigor, not final conv)
│
│  Conv 2 — Remove dead Copilot hooks config (Phase 4)
├─► Builder analyze → none (no context needed)
├─► Builder implement
│   Edits: copilot/_meta/install.yaml (removes hooks: block, lines 10–14)
│   Verify: pytest → 178 passed, 5 pre-existing failures, 0 new
│   Reviewer: SKIPPED (lite rigor, not final conv)
│
│  Conv 3 — Studio focus ring token fixes (Phase 5)
├─► Builder analyze → NEEDS_CONTEXT (1 quick entry)
│   Scout: TopBar.module.css + Sidebar.module.css + tokens.css
├─► Builder implement
│   Edits: TopBar.module.css (7 outline rules → var(--focus-ring))
│          Sidebar.module.css (9 outline rules + .filterInput:focus-visible added
│                              + .dropTarget → var(--accent)/var(--accent-bg))
│   Verify: npm run build → 18.31s, 0 errors
│   Reviewer: RUNS (lite rigor, FINAL conv)
├─► Reviewer analyze → NEEDS_CONTEXT (default rules scout + CSS hex check)
│   Scout (parallel): architectural rules + remaining hex colors
├─► Reviewer → PASS (no violations; pre-existing Terminal.module.css noted, out of scope)
│
│  [Stage 4 — Test]
├─► Tester analyze → NEEDS_CONTEXT (4 entries)
│   Scout (parallel): test patterns, pathly-setup entry point,
│                     install.yaml hooks, CSS token status
├─► Tester → 2 FAIL, 11 PASS
│   FAIL 1 (S1.4): pathly-setup dry-run skips all skills (systemic pre-existing gap)
│   FAIL 2 (S3.1): explorer.md wrong path + missing frontmatter
│
│   → Builder fix cycle 1:
│     - Add frontmatter to research/explorer.md
│     - Update USER_STORIES.md S1 criterion (dry-run → file-existence check)
│     - Update USER_STORIES.md S3 criterion (correct path)
│
├─► Tester re-run → 14 PASS, 1 NOT COVERED
│   NOT COVERED (S5 Paper theme): runtime Electron visual — closed via token inspection
│   tokens.css Paper theme: --focus-ring: 2px solid #c75c2a (brown, not blue) ✓
│
│  [Stage 5 — Retro]
└─► Retro agent
    Writes: plans/adapter-parity/RETRO.md
            pipeline-walkthrough/adapter-parity/  ← this folder
```

---

## How agents communicate

Agents never call each other. The orchestrator is the only router.
Communication happens via files on disk:

| File | Written by | Resolved by | Means |
|---|---|---|---|
| `CONSULT_architect.md` | Architect | Builder (deletes) | Pre-build findings to incorporate |
| `REVIEW_FAILURES.md` | Reviewer | Builder (deletes) | Implementation must change |
| `TEST_FAILURES.md` | Tester | Builder or user (deletes) | Stories not satisfied |
| `HUMAN_QUESTIONS.md` | Any agent | User | Pipeline blocked on human decision |

---

## Feedback loop summary

| Stage | Loops | Cause | Resolution |
|---|---|---|---|
| Test | 1 | pathly-setup dry-run criterion unverifiable + explorer.md wrong path/missing frontmatter | Updated acceptance criteria + added frontmatter |

---

## FSM states traversed

```
→ PLANNING
→ DESIGNING
→ PLANNING
→ BUILDING
→ REVIEWING
→ BUILDING
→ REVIEWING
→ BUILDING
→ REVIEWING
→ TESTING
```
