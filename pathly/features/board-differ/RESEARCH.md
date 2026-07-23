# Research — board-differ

_Agent: research · 2026-07-15_

No external research required. The entire stack is familiar:

- **React/TypeScript + Electron IPC** — established pattern in the codebase (`git:commit-board`
  is the direct analogue for the new `git:show-file` handler).
- **SplitDiff / UnifiedDiff / fileDiffUtils / computeLineDiff** — reused as-is from
  `Editor/DraftDiffViewer/`; no new library needed.
- **Python CliProvider shell-out** — existing pattern in `runner/code_context_cli.py`.
- **Flask blueprint routing** — existing `blueprints/code/query.py` pattern.
- **`git show HEAD:<path>`** — standard Git, well-documented; Windows path normalization is
  a known issue handled by forward-slash normalization in the IPC handler.

The one HIGH-risk unknown — the exact JSON shape of `codebase-memory-mcp cli detect_changes`
(`changed_files`/`impacted_symbols` field names, absolute vs repo-relative path format) —
is resolved by a **local CLI probe** (rollout step 1 in ARCHITECTURE_PROPOSAL.md), not
external research. This is already the first mandated build step.

**Recommendation for design/build:** proceed directly. No new patterns or libraries to evaluate
externally. The architectural decisions are complete (ARCHITECTURE_PROPOSAL.md). The builder
should start with the `detect_changes` probe as specified in rollout step 1.
