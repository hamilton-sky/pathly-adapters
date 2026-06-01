# 03 — Artifact Map: antigravity-adapter

Every file produced or consumed during this pipeline run.

---

## Plan files (FSM persistent state)

| File | Written by | Read by | Purpose |
|---|---|---|---|
| USER_STORIES.md | Planner | Tester | Acceptance criteria — the contract |
| IMPLEMENTATION_PLAN.md | Planner | Builder agents | Exact code changes — the design |
| CONVERSATION_PROMPTS.md | Planner | Builder agents | Verbatim prompts — the instructions |
| PROGRESS.md | Orchestrator | Orchestrator | Conversation status — the checkpoint |
| VERIFY.md | Builder (manually) | FSM verify_gate | Verify command outcome |
| REVIEW.md | Reviewer | FSM require_artifact gate | Code review summary |
| RETRO.md | Retro agent | Humans, /lessons | What we learned — the feedback loop |

---

## Transient feedback files (no longer exist)

| File | Written by | Resolved by | Content summary |
|---|---|---|---|
| SCOPE_VIOLATION.md | FSM scope_gate | Baseline update (conv_start_sha) | dispatch_skill.yaml out-of-scope in diff window |
| TEST_FAILURES.md | Tester | Builder (deleted) | 14 missing skill YAMLs; stale count in USER_STORIES.md |
| HUMAN_QUESTIONS.md | FSM require_artifact gate | User (resolved_files) | REVIEW.md missing |

---

## Source files changed

### Detection and CLI wiring (Convs 1–2, prior sessions)

| File | Stories | What changed |
|---|---|---|
| `src/install_cli/detect.py` | S1.1, S1.2 | Added `"antigravity": [Path.home() / ".gemini" / "antigravity-cli"]` to `_HOST_MARKERS` |
| `src/install_cli/orchestrate.py` | S1.1 | Added `"antigravity"` to `ALLOWED_HOSTS` |

### Adapter config (Conv 1, prior session)

| File | Stories | What changed |
|---|---|---|
| `src/pathly_data/adapters/antigravity/_meta/install.yaml` | S1.1 | Created — host, destination, skills.destination, skills.structure, templates.destination |
| `src/pathly_data/adapters/antigravity/README.md` | S1.1 | Created — install instructions |

### Agent YAMLs (Conv 2, prior session)

| File | Stories | What changed |
|---|---|---|
| `src/pathly_data/adapters/antigravity/_meta/architect.yaml` | S2.1 | Created |
| `src/pathly_data/adapters/antigravity/_meta/builder.yaml` | S2.1 | Created |
| `src/pathly_data/adapters/antigravity/_meta/director.yaml` | S2.1 | Created |
| `src/pathly_data/adapters/antigravity/_meta/explorer.yaml` | S2.1 | Created |
| `src/pathly_data/adapters/antigravity/_meta/planner.yaml` | S2.1 | Created |
| `src/pathly_data/adapters/antigravity/_meta/po.yaml` | S2.1 | Created |
| `src/pathly_data/adapters/antigravity/_meta/quick.yaml` | S2.1 | Created |
| `src/pathly_data/adapters/antigravity/_meta/reviewer.yaml` | S2.1 | Created |
| `src/pathly_data/adapters/antigravity/_meta/scout.yaml` | S2.1 | Created |
| `src/pathly_data/adapters/antigravity/_meta/tester.yaml` | S2.1 | Created |
| `src/pathly_data/adapters/antigravity/_meta/web-researcher.yaml` | S2.1 | Created |

### Skill YAMLs (Convs 3–4, prior session + fix cycle)

| File | Stories | What changed |
|---|---|---|
| `src/pathly_data/adapters/antigravity/_meta/*_skill.yaml` (34 total) | S3.1 | Created — copied verbatim from claude adapter; 14 added in fix cycle |

_The 34 skills include the 20 originally planned plus 14 added in the tester fix cycle to match claude adapter parity: `archive-artifacts`, `back`, `commit`, `debug`, `design`, `explore`, `ff`, `fix`, `fsm-call`, `log-agent-done`, `log`, `quick-fix`, `status`, `team`._

### Test coverage (Conv 4)

| File | Stories | What changed |
|---|---|---|
| `tests/test_setup.py` | S4.1 | Added 3 unit tests: `test_host_markers_cover_antigravity`, `test_detect_antigravity_when_dir_exists`, `test_detect_antigravity_when_dir_missing` |
| `tests/test_e2e_install.py` | S4.1 | Added `@pytest.mark.slow test_antigravity_dry_run_exits_0` |

---

## Artifact flow diagram

```
USER_STORIES.md          ←── what to build
       │
       ▼
IMPLEMENTATION_PLAN.md   ←── how to build it
       │
       ▼
CONVERSATION_PROMPTS.md  ←── exact builder prompts
       │
       ▼
PROGRESS.md              ←── which conversations done
       │
       ▼
VERIFY.md + REVIEW.md    ←── gate artifacts
       │
       ▼
RETRO.md                 ←── what we learned
       │
       ▼
lessons/LESSONS_CANDIDATE.md  ←── promoted patterns → next planner
pipeline-walkthrough/antigravity-adapter/  ←── metrics record → this folder
```
