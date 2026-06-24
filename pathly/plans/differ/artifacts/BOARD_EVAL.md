# Board Evaluation

## Classification
BOTH

## Summary
The board expresses intent to bring a "differ" capability to the Comms Board
(CommandCenter). A `DraftDiffViewer` already exists in the editor layer
(`studio/src/renderer/src/components/Editor/DraftDiffViewer/`) and handles
file-based before/after diffs with hunk-level triage. The board's `artifact_path`
field means every artifact message already carries a file reference — the differ
could show the diff between a committed baseline and an agent-revised version of
that artifact. However, the exact trigger and interaction model for the board
context are undefined: the human question "how should we address the differ for the
board" is a design question, not an implementation ticket.

## Key unknown / risk
What is being diffed and when — agent-revised artifact vs git HEAD, two artifact
versions from different board messages, or a draft produced by a board run — is
not specified, and the answer drives component shape, the new IPC/API surface, and
whether `DraftDiffViewer` can be reused as-is or needs a board-specific adapter.

## Recommended next steps
- Explore the board's artifact model and the editor's DraftDiffViewer to map the
  reuse boundary (what can be shared vs what needs a board-specific wrapper).
- Decide the trigger surface: where on the board does the differ open, and what
  file pair does it compare?
- Implement the board differ component (a read-only or triage-enabled panel) using
  the chosen design, reusing `DraftDiffViewer`'s diff utilities where possible.
