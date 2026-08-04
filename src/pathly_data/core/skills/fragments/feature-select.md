## Selecting the target feature board

Pick which feature board to write to. **Show the user their boards and let them choose — never
guess the target.** This is the shared "which feature?" picker; a skill composes it whenever it
needs a target board from an interactive session.

### 1. List the boards

A feature's home is `pathly/features/<name>/`, and every feature — stood up here or driven by the
app — has one. Enumerate those directories as the **complete, reliable** set of boards:

- List the immediate subdirectories of `pathly/features/` (relative to the project root).
- Skip `.archive/` and the reserved structural names: `features`, `project`, `plans`, `goals`,
  `debugs`, `explorations`, `fixes`, `lessons`, `board-artifacts`, `pipeline-walkthrough`.

Optionally annotate each with its live board state:

```bash
curl -s "http://127.0.0.1:8765/db/features?project_root=<project_root>"
```

That returns rows keyed by a **`feature`** field, each with `state`, `updated_at`, and `cost_usd`
— match on `feature` and show the state next to the name. Note: `/db/features` alone is **not** the
full list (it only covers features with pipeline/DB activity, so a freshly created board is absent),
so use it to *annotate*, never to *enumerate*. If the server is unreachable, just show the directory
names — the disk is the source of truth.

### 2. Show a numbered picker

Render a compact list, most-recent first (by folder mtime), with a create-new row at the end:

```
Which board?
  [1] <feature-a>        <state · updated>
  [2] <feature-b>        …
  …
  [n] ＋ Create a new feature
Reply 1–<n>, or type a feature name:
```

Wait for the user, then resolve `$FEATURE`:

- **a number** → that feature is `$FEATURE`.
- **the ＋ row** → run the **create-feature** flow to stand up a new board, then use it as `$FEATURE`.
- **a typed name that matches** an existing board → use it.
- **a typed name that does not match** → offer to create it (→ create-feature) or re-pick.
- **no boards exist yet** → skip the list: "No boards yet — let's create one." → create-feature.

### 3. Resolve board + scope

For a normal feature board set `board = "feature"` and `scope = $FEATURE`. (A project-level
target — rare from an interactive post — uses `board = "project"` and the normalized project-root
path as `scope`; only take that path if the user explicitly asks for the project board.)

Carry `$FEATURE`, `board`, and `scope` forward — the composing skill stamps them onto its write.
