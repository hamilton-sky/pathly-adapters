# Conversation Prompts — docs-sync

## Conversation 1 — Fix stale claims and add missing sections

**Stories:** S1, S2, S3, S4, S5
**Files you will edit:** `docs/ARCHITECTURE.md`, `docs/PATHLY_ARCHITECTURE.md`, `docs/MULTI_TOOL_DESIGN.md`
**No new files needed.**

---

### Context to read first

Before making any edits, read these files to understand the real layout:

- `C:\Users\Yafit\pathly-adapters\docs\ARCHITECTURE.md`
- `C:\Users\Yafit\pathly-adapters\docs\PATHLY_ARCHITECTURE.md`
- `C:\Users\Yafit\pathly-adapters\docs\MULTI_TOOL_DESIGN.md`
- `C:\Users\Yafit\pathly-adapters\src\install_cli\` (glob to confirm which modules exist)
- `C:\Users\Yafit\pathly-adapters\orchestrator\` (glob to confirm module files)

Confirmed facts from the audit:
- `src/install_cli/materialize.py` exists. The docs reference it without the `src/` prefix.
- `src/pathly_data/` is the real path. Docs show `pathly_data/` (missing `src/`).
- `orchestrator/` is a local module at the repo root containing `eventlog.py`, `events.py`, `state.py`. It is not a separate pip package.
- There is no `pathly-engine` package, no `runners/` directory, no `team_flow/` engine module, no `engine_cli/`.

---

### Edit instructions

#### Fix 1 — `docs/ARCHITECTURE.md` (S1)

In the directory tree (around line 43), change:
```
    ├── materialize.py           ← Writes output files to ~/.claude/, ~/.codex/, etc.
```
to reference `src/install_cli/materialize.py` by updating the surrounding tree to show the `src/` layout (the tree currently shows `install_cli/` as a top-level sibling; it should show `src/install_cli/`).

In the module summary table (around line 100), change the path column for `materialize.py` to show `src/install_cli/materialize.py`.

Also update the other `install_cli/` tree entries (`detect.py`, `stitch.py`, `setup_command.py`) to carry the `src/` prefix if they don't already.

#### Fix 2 — `docs/ARCHITECTURE.md` (S5)

Add a short `orchestrator/` row or callout near the module summary table. Example content:

> `orchestrator/` — local Python module at the repo root. Implements an FSM event-log for tracking LLM conversation context. Not a user-facing CLI tool.

#### Fix 3 — `docs/PATHLY_ARCHITECTURE.md` (S1 + S3)

- In the directory tree (around line 61), prefix `install_cli/` entries with `src/`.
- In the module table (around line 77), prefix all `install_cli/` module names with `src/`.
- In the `pathly_data/` section (around line 84-102), change the tree heading from `pathly_data/` to `src/pathly_data/`. Update any prose sentence in that section that refers to `pathly_data/` without the prefix.

#### Fix 4 — `docs/PATHLY_ARCHITECTURE.md` (S4)

After the existing folder structure section, insert a new section:

```markdown
## Python Package Layout

The repository uses a `src/` layout. The two source packages are:

| Package | Path | Purpose |
|---|---|---|
| `pathly_adapters` | `src/pathly_adapters/` | Install CLI — `pathly-setup` and `pathly-tokens` entry points |
| `pathly_data` | `src/pathly_data/` | Installed package data — agent contracts, skill logic, adapter metadata |

Entry points are declared in `pyproject.toml`. `src/install_cli/` contains the
CLI implementation modules (`detect.py`, `stitch.py`, `materialize.py`,
`setup_command.py`).
```

Adjust wording to fit the existing doc tone. Keep the section under 15 lines.

#### Fix 5 — `docs/MULTI_TOOL_DESIGN.md` (S2)

Replace the "Current Structure" tree (lines 9-31) with a tree that reflects
the real layout:

```text
pathly-adapters/                 ← repo root (single package)
├── src/
│   ├── install_cli/             ← Python CLI: detect, stitch, materialize, setup_command
│   ├── pathly_adapters/         ← pip package entry point
│   └── pathly_data/             ← installed package data
├── core/                        ← single source of truth (tool-agnostic)
│   ├── agents/
│   ├── skills/
│   └── templates/plan/
├── adapters/                    ← thin tool-specific wrappers
│   ├── claude/
│   ├── codex/
│   └── copilot/
├── orchestrator/                ← local FSM event-log module (internal)
├── docs/
└── pyproject.toml
```

Remove the `pathly-engine` row from the adapter table (the CLI row that
references `pathly-engine/engine_cli/`). If no CLI adapter currently exists,
remove the row entirely or note it as roadmap.

Remove all remaining references to: `pathly-engine`, `runners/`, `team_flow/`
(engine side), `engine_cli/`.

---

### Verification commands

Run these after all edits. Each must return the stated result.

```powershell
# S2: no pathly-engine references remain
Select-String -Path "C:\Users\Yafit\pathly-adapters\docs\*" -Pattern "pathly-engine"
# expected: no matches

# S1: all materialize.py references carry src/ prefix
Select-String -Path "C:\Users\Yafit\pathly-adapters\docs\*" -Pattern "install_cli/materialize"
# expected: all matches contain "src/install_cli/materialize"

# S3: pathly_data/ references carry src/ prefix
Select-String -Path "C:\Users\Yafit\pathly-adapters\docs\PATHLY_ARCHITECTURE.md" -Pattern "pathly_data/"
# expected: all matches contain "src/pathly_data/"

# S4: Python Package Layout section exists
Select-String -Path "C:\Users\Yafit\pathly-adapters\docs\PATHLY_ARCHITECTURE.md" -Pattern "Python Package Layout"
# expected: at least 1 match

# S5: orchestrator note exists in ARCHITECTURE.md
Select-String -Path "C:\Users\Yafit\pathly-adapters\docs\ARCHITECTURE.md" -Pattern "orchestrator"
# expected: at least 1 match (the new note)
```

All five checks must pass before marking Conversation 1 complete in `PROGRESS.md`.
