# Board Evaluation — Codebase Diff with Accept/Reject

## Classification
BOTH

## Summary

The user is asking whether the Board Differ should surface a **codebase-wide diff** (all files
changed by a run, not just one artifact) and give the supervisor the ability to **accept or reject**
each change. This is a meaningful scope extension beyond the current MVP plan, which covers one
artifact card → one file diff (read-only). The idea is strongly aligned with the product's headless
supervision premise, is technically feasible, and maps cleanly onto the `detect_changes(project)`
tool the architect identified. However it introduces a destructive operation (reject = discard
uncommitted changes) that needs careful UX gating and should land as a **fast-follow** after the
single-file MVP, not in the first ship.

## Key unknown / risk

"Reject" (git checkout -- `<file>`) permanently discards uncommitted work — the UX must prevent
accidental clicks, and the feature needs a clear recovery path (or refuse reject on files not
created by the current run).

## What the current spec already covers

| Surface | What it gives | Accept/Reject? |
|---|---|---|
| (a) Artifact card → "See changes" | One file, artifact vs HEAD, read-only | No |
| (b) Agent draft vs original | One `.draft` file, per-hunk triage | Yes — per hunk |
| (c) Two artifacts side-by-side | Power compare | No |

The user is asking for something that sits **above** all three surfaces: a **full-repo changed-files
panel** triggered from the run card (not from a single artifact card), listing every file the run
touched, each expandable into its diff, with accept/reject at file granularity.

## Is this a good idea? Yes — here is the case

The headless supervision premise is: the human didn't watch the agent work. At the end of a run,
they see a summary and artifact cards. But an agent run may have touched **10 files** — only one
of which surfaced as a board artifact. The supervisor today has no way to see the other 9 without
opening a terminal.

A codebase-wide diff view closes that gap. It answers: *"what did this run actually do to my
repo, and is any of it wrong?"* That is a legitimate new capability, not a duplicate of anything
that exists.

`detect_changes(project)` already returns `{changed_files, impacted_symbols[], depth}` for the
whole working tree. The architect's recommended implementation (filter detect_changes by file) is
exactly what this feature needs — except applied to **every file in the list**, not just the
artifact's file.

## Recommended shape (no scope explosion)

### Entry point: Run card "Review changes" action (not artifact card)
A second action alongside "View run" — triggers the multi-file view for the whole run's footprint.
This is distinct from the per-artifact "See changes" (surface a) which stays as-is.

### The multi-file panel
```
┌─ Changed files (6)                              ─────────────────────────┐
│  ✓ src/runner/code_context_cli.py    +42 −11   ⚠ 3 callers              │
│  ✓ src/runner/query.py               +8 −2                               │
│  ○ pathly/features/board-differ/…   +120 −0   NEW                       │
│  ○ src/http_server/blueprints/…     +30 −5                               │
│  …                                                                        │
│                                     [Reject file ▼]  [Accept all]        │
└───────────────────────────────────────────────────────────────────────────┘
```

Click a file → inline diff (reuses the same CodeDiffView from surface a).
Impact panel beside it (same ImpactPanel, filtered to that file's symbols).

### Accept vs Reject — right level of granularity for v1

| Action | What it does | Risk level |
|---|---|---|
| **Accept file** | Mark as reviewed (no git op needed — the file stays) | Zero — cosmetic |
| **Accept all** | Mark all reviewed, close panel | Zero |
| **Reject file** | `git checkout -- <file>` (DESTRUCTIVE — discards change) | High |
| Reject hunk | Partial revert (requires apply-patch) | Very high — defer |

**For v1: Accept = cosmetic mark-reviewed (no git). Reject = whole-file discard with a
mandatory confirmation ("This permanently discards uncommitted changes to `<file>`. This
cannot be undone.").** Reject is power-user; the primary flow is review → accept → continue.

### Why NOT hunk-level reject here
Surface (b) already handles hunk-level accept/reject for draft files. The multi-file panel's
job is oversight and whole-file decisions, not surgical editing. Hunk-level here would duplicate
surface (b) and bloat the scope significantly.

## Sequencing

1. **Now: MVP as planned** — single-file "See changes" (surface a) + Impact panel. Ship this
   first; proves the diff+impact loop with minimal risk.
2. **v1.1 fast-follow: Multi-file run overview** — "Review changes" on the run card, file list,
   per-file diff (reuses surface a's CodeDiffView), accept (mark reviewed) + reject (with
   confirmation). This is the answer to the user's question.
3. **Later: Surface (b)** — per-hunk draft-triage for surgical edits.

## Recommended next steps

- Post a `decision` to the board confirming the multi-file review panel as a named fast-follow
  (not cutting it, not blocking the MVP).
- Add a task to the board-differ goal: "Design multi-file run-review panel (Changed Files view,
  file-level accept/reject, IPC for git checkout/status)."
- Update APPROACH.md to add a surface (d) row for the run-level multi-file view.
- Confirm with UX/designer that the "reject" action has a destructive-action pattern (red button,
  modal confirmation, explicit file path in the prompt).
