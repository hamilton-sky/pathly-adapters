# adapter-parity — Retrospective

_Date: 2026-05-25 | Branch: master_

## Plan Quality

**Conversation sizing:** Good — all 3 conversations felt about right, no mid-conversation scope cuts needed.

**Surprises:** Two test failures surfaced that the plan didn't anticipate:
1. **pathly-setup dry-run criterion (S1.4)** — The acceptance criterion assumed `pathly-setup --dry-run --host copilot` would list archive skills in the manifest. In reality, `setup_command.py` emits `[warn] No core skill for 'archive', skipping` for every skill across all three adapters (systemic pre-existing gap — 20+ skills affected). The criterion had to be rewritten to a verifiable file-existence + schema check.
2. **explorer.md wrong path (S3.1)** — The plan specified `src/pathly_data/core/agents/explorer.md` but all core agents live in subdirectories (`research/`, `planning/`, `building/`, etc.). The file was correctly placed at `research/explorer.md`, but the acceptance criterion path was wrong. Additionally, the existing file lacked YAML frontmatter (`name:`, `description:`) that the criterion required.

**Missing from plan:** Nothing specific called out — the conversation sizing and scope were on target.

## What Worked

- Conversation scope was well-calibrated across all 3 convs
- CSS token replacement was clean — builder found all occurrences and the reviewer confirmed zero `#89b4fa` remaining
- hooks removal from install.yaml was safe — scout confirmed `setup_command.py` doesn't reference hooks at all, so no risk
- Full test suite (178 tests) unchanged — no regressions

## What to Improve Next Time

- **Verify CLI command flags before writing acceptance criteria** — `pathly-setup --host copilot` is not valid; host is positional. Run `pathly-setup --help` when writing criteria that depend on CLI behavior.
- **Check actual file paths against existing codebase structure before writing acceptance criteria** — core agents use subdirectories (research/, planning/, etc.); the plan should have said `research/explorer.md`, not `explorer.md`.
- **Check frontmatter requirements for core agent files** — if a criterion requires `name:` and `description:` frontmatter, verify the existing file has it before closing the phase.

## Seed for Next Storm

> adapter-parity delivered Copilot archive/commit skills, Codex commit skill, explorer.md frontmatter, Copilot hooks removal, and Studio focus ring tokenisation. Two post-implementation criterion fixes were needed: pathly-setup dry-run doesn't work for any skills (systemic gap), and core agent files live in research/ subdirectory with frontmatter required. Next work: the 117 parity issues from check_core.py (most core skills/agents lack _meta entries in one or more adapters) and Terminal.module.css focus ring non-compliance.
