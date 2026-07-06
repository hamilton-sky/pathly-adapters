# Board Differ — Architect Consultation

_Architect review of `pathly/features/board-differ/APPROACH.md`, 2026-07-06 (code-grounded)._

## Verdict
Surface (a) + graceful-degraded Impact panel is buildable and worth doing; but the spec's central claim — `op:"impact" → detect_changes(target)` giving *artifact-vs-HEAD* impact — is **not compatible with the tool as it stands**, the `detect_changes` op **does not exist in the backend yet**, and the frontend viewer it names cannot render a code diff. The "~20 lines" estimate is off by a large factor.

## Feasibility (surface by surface)
- **(a) Artifact vs git HEAD — feasible, but not by reusing the named component.** `useDraftDiff` reads *two files off disk* via `window.pathly.fs.read()` and diffs them by **markdown `## ` section**, not by line/hunk. There is no git baseline in the read path and no line-level diff. To show "artifact vs HEAD" you must produce the HEAD blob (an IPC that does not exist — main process only exposes `fs:read`; grep for `git show`/`simple-git` → zero hits) and diff it. `CodeDiffView` consumes section-hunks, inheriting the same limitation. **A new diff path, not a config of the existing one.**
- **(b) draft-triage — feasible and is the component's actual native mode.** `DraftDiffViewer` already does accept/reject/reconstruct/apply on an `(originalPath, draftPath)` pair. Ironically (b), which the spec defers, is the *lowest-friction* reuse; (a), which it ships first, fights the component's grain.
- **(c) two artifacts — feasible, same as (b)** with a second-file picker. Low marginal cost once (b) exists.
- **Impact panel — feasible only in degraded/structure form today.** `op:"impact"` is gated open (`query.py:47`) but `code_query` sends *every* op through `build_block → query_graph` (`query.py:223` → `code_context_cli.py:143`). It returns a symbol/caller-count structure block, **never `detect_changes`**. A panel wired today shows "symbols in this file + in/out degree," not "this change touches these 3 callers / this flow." The differentiated framing needs new backend code.

## Key risks (prioritized)
1. **The `detect_changes` contract mismatch is real and load-bearing** — the headline value depends on a mapping the tool does not offer.
2. **No git baseline in the app at all.** Surface (a) is blocked on a new main-process git bridge (`git show HEAD:<path>`, untracked-file handling).
3. **Component reuse overstated for (a).** Section-level markdown diff ≠ code line-diff; the spec conflates them.
4. **New / untracked artifacts have no HEAD blob** → `git show HEAD:<path>` errors on the common case (agent wrote a new file). Needs an explicit "new file — all additions" branch.
5. **"Artifact" ≠ "working-tree file."** A board artifact is a `comms_artifacts.path` row; nothing guarantees it equals the working tree at view time. `detect_changes` only sees the working tree.
6. **`_content_hash`/cache assume `target` is a readable path**; a symbol-style or new-file target degrades the cache key (works, just note it).

## The `detect_changes` question — finding
- **The op is not implemented.** `CliProvider` has one query method (`build_block → query_graph`). No `detect_changes` call anywhere; `code_query` ignores `op` for routing — impact and callers hit the identical code path.
- **The tool's `detect_changes` is working-tree-vs-HEAD, whole-repo.** `{project}` in → `{changed_files, impacted_symbols[], depth}` out. It does not take a target file, a diff, or a hypothetical change.
- **Therefore "impact of artifact-vs-HEAD" does not map onto it** unless the artifact *is* the current dirty working-tree state of that path — incidental for a just-finished run, collapses once the tree is clean or the artifact is one of several dirty files.

Right design, in order of endorsement:
- **Best now — scope to working-tree, filter to the file:** call `detect_changes(project)` and *filter* `impacted_symbols` to the diffed artifact's path. Honest to the tool; correct whenever the artifact equals the dirty file. Label truthfully: "impact of current uncommitted changes in this file." Do not claim per-hunk or hypothetical impact.
- **Acceptable — apply-to-worktree:** surface (b) applying accepted hunks *does* dirty the tree, so `detect_changes` afterward is genuinely correct. That makes (b) the better natural fit for real impact than (a).
- **Avoid for v1 — synthetic-diff support:** feeding a hypothetical diff into the graph is a code-intel-initiative-sized change, not a differ feature.

## Recommendations
- **Smallest safe first slice — flip the spec's order to (b), and diff markdown.** Ship draft-triage on `.md` artifacts using the existing `DraftDiffViewer` unchanged. Zero backend, zero git, zero new IPC, real value.
- **Then surface (a) as a separate, explicitly-scoped build:** a main-process git bridge (`git:showHead(path)` → blob or `null` for untracked; register in `ipc/`, preload, `global.d.ts`) + a code-hunk diff path (don't overload `useDraftDiff`'s section model). Treat "new file → all-additions" as first-class.
- **Impact panel: ship the degraded form first, correctly labeled.** Wire `ImpactPanel` to `code/query op:"impact"` as it behaves today (structure/callers) with graceful-off. Add a **real** `CliProvider.detect_changes(project)` + a `code_query` branch routing `op:"impact"` to it and **filtering by file** as a distinct task — ~60–100 LOC (provider method + route split + parse + filter + test), not ~20.
- **Keep the code/ blueprint boundary intact.** `detect_changes` on `CliProvider` (`runner/code_context_cli.py`), a routing branch in `code_query` (`http_server/blueprints/code/query.py`) — don't let the HTTP handler shell out or parse git (violates `http_server → runner` direction). Role gate, board logging, never-500 reuse as-is.
- **Non-code / markdown artifacts:** text diff, no Impact panel — gate the panel on file extension / on `detect_changes` returning symbols for that path.

## Open technical questions
1. Baseline for (a): **HEAD blob** or **run-start commit**? If runs span multiple commits (team mode), HEAD-vs-artifact understates the run's change — persist a run-start SHA?
2. Are we willing to state the panel's true scope — "impact of the current uncommitted change to this file" — or does the value prop *require* per-hunk/hypothetical impact the tool can't give without new engine work? That answer decides whether (a)-first is even the right sequencing, or whether (b) should carry the impact story.
