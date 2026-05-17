# IMPLEMENTATION_PLAN.md — pathly-commands-v2

_Rigor: standard — 5 conversations._

**Prerequisite:** `mcp-fsm-driver` all 4 conversations complete. Verify:
```bash
python -c "from pathly_orchestrator.mcp_server import next_action, complete_stage; print('OK')"
grep "next_action\|complete_stage" src/pathly_data/core/skills/team.md
```

**Surface note:** All Python CLI scripts work on every surface (Claude Code CLI,
Desktop App, VS Code Extension, Codex) because the LLM skill wrappers call them
via the Bash tool. The user types `/pathly status` in a conversation — the skill
runs `pathly-status` via Bash and prints the output. Also callable directly from
any terminal without opening a conversation.

**Menu spec:** Skill files that display state must read
`pathly/plans/mcp-fsm-driver/CONTEXTUAL_MENU_UX.md` for the exact panel format.

---

## Conversation 1 — Python CLI: `pathly-status` + `pathly-log`

**Stories:** S1, S2

**Scope:** Two Python CLI scripts + two thin skill wrappers. No LLM reasoning —
the scripts do all computation; the skill just calls them via Bash.

**Natural seam:** After this conversation users can check state and read event
history from any surface, in or out of a conversation.

### Files to create

| File | Type | Change |
|------|------|--------|
| `src/pathly_orchestrator/status_cli.py` | Python | Cross-feature dashboard |
| `src/pathly_orchestrator/log_cli.py` | Python | Readable event timeline |
| `src/pathly_data/core/skills/status.md` | Skill wrapper | Calls `pathly-status` via Bash |
| `src/pathly_data/core/skills/log.md` | Skill wrapper | Calls `pathly-log` via Bash |
| `src/pathly_data/adapters/claude/_meta/status_skill.yaml` | Adapter | Claude |
| `src/pathly_data/adapters/claude/_meta/log_skill.yaml` | Adapter | Claude |
| `src/pathly_data/adapters/codex/_meta/status_skill.yaml` | Adapter | Codex |
| `src/pathly_data/adapters/codex/_meta/log_skill.yaml` | Adapter | Codex |
| `src/pathly_data/adapters/copilot/_meta/status_skill.yaml` | Adapter | Copilot |
| `src/pathly_data/adapters/copilot/_meta/log_skill.yaml` | Adapter | Copilot |
| `pyproject.toml` | Edit | Add `pathly-status` and `pathly-log` entry points |

### `status_cli.py` — what to implement

```python
"""pathly-status — cross-feature dashboard. Entry point: main()."""
import argparse, json
from pathlib import Path

SCAN_ROOTS = ["pathly/plans", "pathly/debugs", "pathly/explorations"]
FEEDBACK_PRIORITY = [
    "HUMAN_QUESTIONS", "BLOCKED_ON_HUMAN", "ARCH_FEEDBACK",
    "DESIGN_QUESTIONS", "IMPL_QUESTIONS", "REVIEW_FAILURES", "TEST_FAILURES",
]

def main():
    parser = argparse.ArgumentParser(description="Pathly cross-feature dashboard")
    parser.add_argument("--all", action="store_true", help="Include DONE topics")
    args = parser.parse_args()

    cwd = Path.cwd()
    rows = []
    for root in SCAN_ROOTS:
        for state_file in sorted((cwd / root).glob("*/STATE.json"),
                                 key=lambda p: p.stat().st_mtime, reverse=True):
            if ".archive" in str(state_file):
                continue
            try:
                state = json.loads(state_file.read_text())
            except Exception:
                continue
            topic = state_file.parent.name
            flow = root.split("/")[-1].rstrip("s")  # plans→plan→team by mapping
            flow = {"plans": "team", "debugs": "debug",
                    "explorations": "explore"}.get(root.split("/")[-1], root)
            current = state.get("current", "?")
            conv = state.get("current_conversation", 0)
            # Check feedback
            feedback_dir = state_file.parent / "feedback"
            blocking = None
            if feedback_dir.is_dir():
                present = {f.stem for f in feedback_dir.glob("*.md")}
                for name in FEEDBACK_PRIORITY:
                    if name in present:
                        extra = len(present) - 1
                        blocking = name + (f" (+{extra} more)" if extra else "")
                        break
            rows.append((topic, flow, current, conv, blocking))

    done = [r for r in rows if r[2] == "DONE"]
    active = [r for r in rows if r[2] != "DONE"]

    if not rows:
        print("Nothing in progress.")
        return

    print("─" * 57)
    print("  Pathly · Active features")
    print("─" * 57)
    for topic, flow, current, conv, blocking in active:
        tag = f"[BLOCKED: {blocking}]" if blocking else f"(conv {conv})"
        print(f"  {topic:<24} ·  {flow:<8} ·  {current:<18} {tag}")
    if args.all and done:
        for topic, flow, _, conv, _ in done:
            print(f"  {topic:<24} ·  {flow:<8} ·  DONE ✓")
    print("─" * 57)
    if not args.all and done:
        print(f"  ({len(done)} DONE topic(s) hidden — use --all to show)")
```

### `log_cli.py` — what to implement

```python
"""pathly-log — readable EVENTS.jsonl timeline. Entry point: main()."""
import argparse, json
from datetime import datetime
from pathlib import Path

SCAN_ROOTS = {"pathly/plans": "team", "pathly/debugs": "debug",
              "pathly/explorations": "explore"}

def render_event(evt: dict) -> str:
    ts_raw = evt.get("ts", "")
    try:
        ts = datetime.fromisoformat(ts_raw).strftime("%H:%M:%S")
    except Exception:
        ts = "??"
    etype = evt.get("type", "UNKNOWN")
    if etype == "STATE_TRANSITION":
        detail = f"{evt.get('from', '?')} → {evt.get('to', '?')}"
    elif etype == "STATE_ROLLBACK":
        detail = f"{evt.get('from', '?')} → {evt.get('to', '?')}"
    elif etype == "DECIDE_ROUTING":
        detail = (f"chosen: {evt.get('chosen', '?')}  "
                  f"(input: \"{evt.get('decision_input', '?')}\")")
    elif etype == "FEEDBACK_RESOLVED":
        detail = f"{evt.get('file', '?')}  agent: {evt.get('agent', '?')}"
    elif etype == "NEEDS_CONTEXT":
        detail = f"count: {evt.get('count', '?')}"
    else:
        detail = "  ".join(f"{k}: {v}" for k, v in evt.items()
                           if k not in ("type", "ts"))
    return f"  {ts}  {etype:<24} {detail}"

def main():
    parser = argparse.ArgumentParser(description="Pathly event timeline")
    parser.add_argument("topic", nargs="?", help="Topic name")
    parser.add_argument("--all", action="store_true", help="Show full history")
    args = parser.parse_args()

    cwd = Path.cwd()
    storage_path = None
    flow = "?"

    if args.topic:
        for root, f in SCAN_ROOTS.items():
            candidate = cwd / root / args.topic
            if candidate.is_dir():
                storage_path, flow = candidate, f
                break
    else:
        # Most recently modified STATE.json
        best = None
        for root, f in SCAN_ROOTS.items():
            for sf in (cwd / root).glob("*/STATE.json"):
                if ".archive" in str(sf):
                    continue
                if best is None or sf.stat().st_mtime > best[0]:
                    best = (sf.stat().st_mtime, sf.parent, f)
        if best:
            _, storage_path, flow = best

    if storage_path is None:
        print("No active topic found. Pass a topic name or start a feature first.")
        return

    events_file = storage_path / "EVENTS.jsonl"
    if not events_file.exists():
        print(f"No events recorded for {storage_path.name}.")
        return

    lines = events_file.read_text().splitlines()
    total = len(lines)
    shown = lines if args.all else lines[-20:]

    print("─" * 57)
    print(f"  Pathly log · {storage_path.name} · {flow}")
    print("─" * 57)
    for line in shown:
        try:
            evt = json.loads(line)
            print(render_event(evt))
        except Exception:
            print(f"  [parse error] {line}")
    print("─" * 57)
    if not args.all and total > 20:
        print(f"  Showing last 20 of {total} events. Use --all for full history.")
```

### Skill wrappers — shape for both

Each skill wrapper is two sections only:

```markdown
# <name>

<one-line description>

## Runtime

Run: pathly-<name> $ARGUMENTS
Print the output exactly as returned.
If the command is not found: print "Run pathly-setup first to install Pathly CLI tools."
```

### `pyproject.toml` additions

In `[project.scripts]`, after `pathly-fsm`:
```toml
pathly-status = "pathly_orchestrator.status_cli:main"
pathly-log    = "pathly_orchestrator.log_cli:main"
```

### Verify after Conv 1

```bash
python -c "from pathly_orchestrator.status_cli import main; print('OK')"
python -c "from pathly_orchestrator.log_cli import main; print('OK')"
grep "pathly-status\|pathly-log" pyproject.toml
grep "pathly-status" src/pathly_data/core/skills/status.md
pytest -q
```

---

## Conversation 2 — Python CLI: `pathly-back` + `pathly-ff`

**Stories:** S4, S5

**Scope:** Two Python CLI scripts + two thin skill wrappers. `pathly-back` reads
EVENTS.jsonl and writes STATE.json with `input()` confirmation. `pathly-ff` calls
`complete_stage` via the MCP server's Python API; if `{decide: true}` is returned
it prompts via `input()` — no LLM needed.

**Natural seam:** After this conversation the two most common FSM corrections
(roll back, skip forward) work from any terminal without opening a conversation.

### Files to create

| File | Type | Change |
|------|------|--------|
| `src/pathly_orchestrator/back_cli.py` | Python | One-state rollback |
| `src/pathly_orchestrator/ff_cli.py` | Python | Fast-forward via MCP |
| `src/pathly_data/core/skills/back.md` | Skill wrapper | Calls `pathly-back` |
| `src/pathly_data/core/skills/ff.md` | Skill wrapper | Calls `pathly-ff` |
| `src/pathly_data/adapters/claude/_meta/back_skill.yaml` | Adapter | Claude |
| `src/pathly_data/adapters/claude/_meta/ff_skill.yaml` | Adapter | Claude |
| `src/pathly_data/adapters/codex/_meta/back_skill.yaml` | Adapter | Codex |
| `src/pathly_data/adapters/codex/_meta/ff_skill.yaml` | Adapter | Codex |
| `src/pathly_data/adapters/copilot/_meta/back_skill.yaml` | Adapter | Copilot |
| `src/pathly_data/adapters/copilot/_meta/ff_skill.yaml` | Adapter | Copilot |
| `pyproject.toml` | Edit | Add `pathly-back` and `pathly-ff` entry points |

### `back_cli.py` — what to implement

Read existing `pathly_orchestrator.eventlog` and `state.py` before writing —
reuse their helpers where possible.

Steps:
1. Parse optional `topic` from `sys.argv`. Auto-detect if absent (same scan as
   `status_cli.py` — use the most recently modified non-DONE STATE.json).
2. Locate `storage_path` from STATE.json `flow` field + flow YAML `storage_path`
   template. Or infer from directory path.
3. Read `EVENTS.jsonl`. Scan newest→oldest for first `STATE_TRANSITION` event.
   Extract `from` field = `prior_state`.
   If none found: print message, exit 0.
4. Read STATE.json `current` field.
5. Print confirmation. Call `input("Proceed? (y/n): ")`. On "n": exit 0.
6. Write STATE.json atomically (write `.tmp` → rename).
   Set `current = prior_state`. Update `updated_at`. Preserve all other fields.
7. Append `{"type": "STATE_ROLLBACK", "from": current, "to": prior_state,
            "ts": <ISO UTC now>}` to EVENTS.jsonl.
8. Print: `"Rolled back <topic>: <current> → <prior_state>"`
   Print: `"Note: git commits are not undone. Run /pathly go to resume."`

### `ff_cli.py` — what to implement

Import and call `complete_stage` from `pathly_orchestrator.mcp_server` directly
(not via the MCP protocol — just a regular Python function call).

Steps:
1. Parse topic (auto-detect if absent). Resolve `flow`, `project_root = str(Path.cwd())`.
2. Call `next_action(flow, topic, project_root)`.
   If `blocked`: print blocked state and "Use pathly-fix to resolve." Exit 0.
3. Read flow YAML to evaluate what the next state would be (L1 check only —
   just show the user what is likely to happen). Print:
   `"Fast-forward <topic>: <current_state> → <likely_next>"`
   If `transition_actions` has `git_commit` for this transition: print the warning.
4. `input("Proceed without running the current agent? (y/n): ")`. On "n": exit 0.
5. Call `complete_stage(flow, topic, project_root)`.
   - If `{"decide": True, ...}` returned:
       print the question + context + options.
       answer = `input("Your choice [<keys>]: ")`.strip()
       call `complete_stage(flow, topic, project_root, decision=answer)`.
   - If `{"done": True}`: print "Feature complete."
   - Otherwise: print "Advanced to: <next_state>  Agent: <agent>"

### `pyproject.toml` additions

```toml
pathly-back = "pathly_orchestrator.back_cli:main"
pathly-ff   = "pathly_orchestrator.ff_cli:main"
```

### Verify after Conv 2

```bash
python -c "from pathly_orchestrator.back_cli import main; print('OK')"
python -c "from pathly_orchestrator.ff_cli import main; print('OK')"
grep "pathly-back\|pathly-ff" pyproject.toml
pytest -q
```

---

## Conversation 3 — LLM skill: `fix`

**Stories:** S3

**Scope:** One LLM skill file. `fix` spawns an agent — it cannot be Python CLI.
Thin wrappers are not applicable here; this is a full skill.

### Files to create

| File | Type | Change |
|------|------|--------|
| `src/pathly_data/core/skills/fix.md` | LLM skill | Feedback resolver |
| `src/pathly_data/adapters/claude/_meta/fix_skill.yaml` | Adapter | Claude |
| `src/pathly_data/adapters/codex/_meta/fix_skill.yaml` | Adapter | Codex |
| `src/pathly_data/adapters/copilot/_meta/fix_skill.yaml` | Adapter | Copilot |

### `fix.md` — what to implement

Read before writing:
- `src/pathly_data/core/skills/team.md` (topic resolution + MCP call pattern)
- `pathly/plans/mcp-fsm-driver/CONTEXTUAL_MENU_UX.md` (Scenario 2 blocked panel)

Steps:
1. Resolve TOPIC (auto-detect if absent). Resolve `flow`, `project_root`.
2. Call `next_action(flow, topic, project_root)`.
3. If not blocked: "No open feedback for `<topic>`. Use /pathly go to continue." Exit.
4. If `target_agent == "human"`: print file contents.
   Print: "Human decision required — resolve manually, delete `feedback/<file>`,
   then run /pathly go." Exit.
5. If `target_agent == <agent>`:
   Display Scenario 2 panel from CONTEXTUAL_MENU_UX.md.
   Options:
     [1] Resolve  — run <agent> on the feedback file
     [2] View     — print file contents, show menu again
     [3] Escalate — write HUMAN_QUESTIONS.md with escalation note, halt
     [4] Abort    — exit

6. On [1]: follow returned instructions as <agent>.
   After agent completes: delete `feedback/<file>`. Print "Deleted: feedback/<file>"
   Call `complete_stage(flow, topic, project_root)`.
     - If blocked again: show blocked panel, loop.
     - If `{decide: true}`: show Scenario 3 Panel A, wait for answer,
       call `complete_stage(... decision=<answer>)`.
     - Otherwise: show resulting state panel.
     - If `done=true`: "Feature complete."

### Verify after Conv 3

```bash
grep "complete_stage" src/pathly_data/core/skills/fix.md
grep "HUMAN_QUESTIONS" src/pathly_data/core/skills/fix.md
grep "target_agent" src/pathly_data/core/skills/fix.md
```

---

## Conversation 4 — `meet` enhancement: escalate to pipeline

**Stories:** S6

**Scope:** Edit `meet.md` Step 5 only. Add option `[5] Escalate to pipeline`.
No new files. No Python changes.

### Files to edit

| File | Change |
|------|--------|
| `src/pathly_data/core/skills/meet.md` | Add Step 5 option [5] |

### What to add to Step 5

Read `meet.md` in full before editing. Read the active flow YAML to know which
feedback types map to which agents.

Replace the existing Step 5 print block with this expanded version:

```
What do you want to do next?

[1] Return to <current stage>
[2] Promote to planner update
[3] Promote to architecture update
[4] Ask another meet question
[5] Escalate to pipeline    ← NEW
[6] See all commands
```

Implement option [5] as follows:
1. Ask: "Which feedback type fits this consultation?
     [1] ARCH_FEEDBACK      → routes to architect
     [2] DESIGN_QUESTIONS   → routes to architect
     [3] IMPL_QUESTIONS     → routes to planner
   Reply with 1–3:"
2. Map the choice to the filename: `ARCH_FEEDBACK.md` / `DESIGN_QUESTIONS.md` /
   `IMPL_QUESTIONS.md`.
3. Read the consult note already written to `plans/$FEATURE/consults/<timestamp>-<role>.md`.
4. If `feedback/<chosen>.md` already exists: append with separator
   `\n---\n## Consultation added <timestamp>\n`. Do not overwrite.
   If absent: write the file fresh.
5. Print:
   ```
   Pipeline blocked on feedback/<chosen>.md
   Next complete_stage will route to: <agent>  (from flow feedback_routing)
   Use /pathly fix or /pathly go to continue.
   ```
6. The `consults/` file is preserved — escalation is additive.

### Verify after Conv 4

```bash
grep "Escalate to pipeline" src/pathly_data/core/skills/meet.md
grep "ARCH_FEEDBACK\|DESIGN_QUESTIONS\|IMPL_QUESTIONS" src/pathly_data/core/skills/meet.md
grep "feedback_routing" src/pathly_data/core/skills/meet.md
```

---

## Conversation 5 — Update start / pause / end / go

**Stories:** S7

**Scope:** Deferred from mcp-fsm-driver Conv 3. Add contextual state panel to
four existing entry-point skills. Edits only — no new files.

Read `pathly/plans/mcp-fsm-driver/CONTEXTUAL_MENU_UX.md` before touching any file.

### Files to edit

| File | Change |
|------|--------|
| `src/pathly_data/core/skills/go.md` | Full panel (4 options) after state recovery |
| `src/pathly_data/core/skills/pause.md` | Read-only panel before writing PAUSED |
| `src/pathly_data/core/skills/end.md` | Read-only summary panel before retro prompt |
| `src/pathly_data/core/skills/start.md` | Full panel when user picks option [4] |

### `go.md` — add after state recovery, before routing

1. Call `next_action(flow, topic, project_root)`.
2. Display Scenario 1 panel (all 4 options).
3. On [1]/Enter: route to flow skill. On [2]: call pause. On [3]: print
   STATE.json + last 10 EVENTS.jsonl lines, show panel again. On [4]: show
   flow switch options.

### `pause.md` — add before writing PAUSED

Display read-only panel:
```
─────────────────────────────────────────────────────────
  Pathly  ·  <flow>  ·  <topic>
  State : <current_state>      Conv : <N>
  Pausing session.
─────────────────────────────────────────────────────────
```
Read STATE.json directly — do NOT call `next_action`.

### `end.md` — add before retro prompt

Call `next_action`. Print read-only summary panel (state, conv count, feedback
warning if any). Then "Write a retro? (y/n)" as before.

### `start.md` — add when user picks [4]

Auto-detect active feature. Call `next_action`. Display Scenario 1 full panel.

### Verify after Conv 5

```bash
grep "next_action" src/pathly_data/core/skills/go.md
grep "Pausing session" src/pathly_data/core/skills/pause.md
grep "next_action" src/pathly_data/core/skills/end.md
grep "next_action" src/pathly_data/core/skills/start.md
```

---

## Overall verify (after all 5 conversations)

```bash
python -c "from pathly_orchestrator.status_cli import main; print('OK')"
python -c "from pathly_orchestrator.log_cli import main; print('OK')"
python -c "from pathly_orchestrator.back_cli import main; print('OK')"
python -c "from pathly_orchestrator.ff_cli import main; print('OK')"
grep "pathly-status\|pathly-log\|pathly-back\|pathly-ff" pyproject.toml
grep "complete_stage" src/pathly_data/core/skills/fix.md
grep "Escalate to pipeline" src/pathly_data/core/skills/meet.md
grep "next_action" src/pathly_data/core/skills/go.md
pytest -q
```
